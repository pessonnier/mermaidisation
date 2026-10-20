import copy
import json
import os
from pathlib import Path
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch
from bpmn_mermaid.vision import extract
from bpmn_mermaid.html_export import export_html
MODEL=json.loads((Path(__file__).parents[1]/'examples/model.json').read_text())
PNG=b'\x89PNG\r\n\x1a\nfixture'
class ProviderTests(unittest.TestCase):
    def test_missing_key(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaisesRegex(ValueError,'OPENAI_API_KEY'): extract(PNG,provider='openai')
    def test_bad_provider(self):
        with self.assertRaises(ValueError): extract(PNG,provider='unknown')
    def test_remote_http_key_rejected(self):
        with self.assertRaisesRegex(ValueError,'HTTPS'): extract(PNG,provider='openai',api_key='test',endpoint='http://example.com/v1')
    def test_openai_protocol_errors_and_redirects(self):
        calls=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                calls.append((self.path,self.headers.get('Authorization'),json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                if self.path.startswith('/redirect'):
                    self.send_response(302);self.send_header('Location','/leak');self.end_headers();return
                self.send_response(200);self.end_headers()
                finish='length' if self.path.startswith('/truncated') else 'stop'
                self.wfile.write(json.dumps({'choices':[{'finish_reason':finish,'message':{'content':json.dumps(MODEL)}}]}).encode())
            def log_message(self,*args): pass
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            with patch.dict(os.environ,{'OPENAI_API_KEY':'test-key','OPENAI_MODEL':'test-vision','OPENAI_BASE_URL':base+'/v1'}):
                self.assertEqual(extract(PNG,provider='openai'),MODEL)
            path,key,payload=calls[0]
            self.assertEqual(path,'/v1/chat/completions');self.assertEqual(key,'Bearer test-key')
            self.assertEqual(payload['model'],'test-vision');self.assertFalse(payload['store'])
            self.assertEqual(payload['response_format'],{'type':'json_object'})
            self.assertTrue(payload['messages'][0]['content'][1]['image_url']['url'].startswith('data:image/png;base64,'))
            with self.assertRaisesRegex(ValueError,'incomplète'): extract(PNG,provider='openai',api_key='test',endpoint=base+'/truncated')
            with self.assertRaisesRegex(ValueError,'302'): extract(PNG,provider='openai',api_key='test',endpoint=base+'/redirect')
            self.assertEqual(len(calls),3)
        finally:
            server.shutdown();server.server_close();thread.join()
class HtmlTests(unittest.TestCase):
    def test_embedded_engine_model_no_remote_scripts(self):
        page=export_html(MODEL)
        self.assertIn('Mermaid',page)
        self.assertIn('type="application/json"',page)
        self.assertNotIn('<script src=',page)
        self.assertIn('connect-src \'none\'',page)
        self.assertGreater(len(page),1000000)
    def test_hostile_label_stays_json(self):
        m=copy.deepcopy(MODEL);m['nodes'][0]['label']='</script><script>window.pwned=1</script>@@VENDOR@@'
        page=export_html(m)
        self.assertNotIn('</script><script>window.pwned',page)
        self.assertIn('\\u003c/script',page)
        self.assertEqual(page.count('id="payload"'),1)
