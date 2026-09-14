import unittest
import time
import io
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from discussion import Memory, parse_answer, is_addressed, request_json, ServiceError, ask_model

class DiscussionTests(unittest.TestCase):
    def test_responses_payload_and_output(self):
        config={'model_endpoint':'https://ai.api.cloud.yandex.net/v1/responses', 'model':'gpt://folder/aliceai-llm/latest','project':'folder'}
        output={'status':'completed','output':[
            {'type':'reasoning','summary':[]},
            {'type':'message','role':'assistant','content':[{'type':'output_text','text':'{"answer":"ok","tasks":[]}'}]}]}
        with patch('discussion.request_json',return_value=output) as api:
            self.assertEqual(ask_model(config,{'request':'test'},'FAKE'),('ok',[]))
            payload=api.call_args.args[1]
            self.assertIs(payload['store'],False)
            self.assertEqual(payload['max_output_tokens'],5000)
            self.assertNotIn('messages',payload)
            # GPT-5 models reject 'temperature' outright — verified on the live API.
            self.assertNotIn('temperature',payload)
            self.assertEqual(api.call_args.kwargs['project'],'folder')

    def test_incomplete_response_never_creates_tasks(self):
        with patch('discussion.request_json',return_value={'status':'incomplete','output':[]}):
            with self.assertRaises(ServiceError):
                ask_model({'model_endpoint':'https://example.com/responses','model':'test'}, {}, 'FAKE')

    def test_chat_completions_compatibility(self):
        with patch('discussion.request_json',return_value={'choices':[{'message':{'content':'{"answer":"ok","tasks":[]}'},'finish_reason':'stop'}]}):
            self.assertEqual(ask_model({'model_endpoint':'https://example.com/chat/completions','model':'test'}, {}, 'FAKE'),('ok',[]))

    def test_network_reset_diagnostic(self):
        with patch('discussion.urlopen', side_effect=URLError(ConnectionResetError('SECRET'))):
            with self.assertRaises(ServiceError) as error:
                request_json('https://ai.api.cloud.yandex.net/v1/chat/completions', {})
            self.assertIn('принудительно разорвано', str(error.exception))
            self.assertNotIn('SECRET', str(error.exception))

    def test_yandex_auth(self):
        with patch('discussion.urlopen') as opened:
            opened.return_value.__enter__.return_value = io.BytesIO(b'{"ok":true}')
            request_json('https://ai.api.cloud.yandex.net/v1/chat/completions', {}, 'FAKE-KEY')
            self.assertEqual(opened.call_args.args[0].get_header('Authorization'),'Api-Key FAKE-KEY')

    def test_secret_free_error(self):
        secret_url='https://api.telegram.org/botFAKE-SECRET/getMe'
        with patch('discussion.urlopen', side_effect=HTTPError(secret_url,401,'FAKE-SECRET',{},None)):
            with self.assertRaises(ServiceError) as error:
                request_json(secret_url,{})
            self.assertIn('401',str(error.exception))
            self.assertNotIn('FAKE-SECRET',str(error.exception))

    def test_fenced_json(self):
        self.assertEqual(parse_answer('```json\n{"answer":"ok","tasks":[]}\n```'),('ok',[]))

    def test_context_isolation_and_edits(self):
        m=Memory(':memory:')
        base={'chat':{'id':1},'message_id':10,'from':{'id':7,'first_name':'A'},'date':int(time.time()),'text':'old'}
        m.remember(base)
        m.remember(dict(base,text='new'))
        m.remember(dict(base,chat={'id':2},text='other group'))
        self.assertEqual([x['text'] for x in m.context(1)],['new'])

    def test_confirmation_auth_and_idempotence(self):
        m=Memory(':memory:')
        pid=m.propose(1,7,{'title':'Task','owner':None,'due':None})
        m.decide(pid,2,7,True)
        m.decide(pid,1,8,True)
        self.assertEqual(m.db.execute('SELECT state FROM proposals').fetchone()[0],'pending')
        m.decide(pid,1,7,True)
        m.decide(pid,1,7,False)
        self.assertEqual(m.db.execute('SELECT state FROM proposals').fetchone()[0],'confirmed')
        self.assertEqual(m.db.execute('SELECT count(*) FROM proposals').fetchone()[0],1)

    def test_expired_confirmation(self):
        m=Memory(':memory:')
        pid=m.propose(1,7,{'title':'Task'})
        m.db.execute('UPDATE proposals SET created=0')
        m.decide(pid,1,7,True)
        self.assertEqual(m.db.execute('SELECT state FROM proposals').fetchone()[0],'expired')

    def test_no_spontaneous_answer(self):
        self.assertTrue(is_addressed({'text':'Bot, what can you do?'},'brb_team_admin_bot',123))
        self.assertFalse(is_addressed({'text':'Обсудим завтра'},'brb_team_admin_bot',123))
        self.assertTrue(is_addressed({'text':'Бот, подведи итог'},'brb_team_admin_bot',123))
        self.assertTrue(is_addressed({'text':'да','reply_to_message':{'from':{'id':123}}},'brb_team_admin_bot',123))

    def test_model_schema(self):
        answer,tasks=parse_answer('{"answer":"Нужен срок", "tasks":[{"title":"Материалы","owner":null,"due":null}]}')
        self.assertIsNone(tasks[0]['due'])
        for raw in ['{}','{"answer":"ok","tasks":"bad"}','{"answer":"ok","tasks":[{"title":"test","due":"2026-02-30"}]}']:
            with self.assertRaises((ValueError,TypeError)):
                parse_answer(raw)

if __name__=='__main__':
    unittest.main()
