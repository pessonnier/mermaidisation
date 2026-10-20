import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch
from bpmn_mermaid.core import render, review, validate, KINDS
from bpmn_mermaid.vision import extract
from bpmn_mermaid.cli import main
MODEL = json.loads((Path(__file__).parents[1] / 'examples/model.json').read_text())
class Tests(unittest.TestCase):
    def setUp(self): self.m = copy.deepcopy(MODEL)
    def test_lanes_and_loop(self):
        text = render(self.m)
        self.assertEqual(text.count('subgraph'),3)
        self.assertIn('v6 --> v5',text)
        self.assertIn('-->|"Non"|',text)
    def test_duplicate(self):
        self.m['nodes'][0]['id']='p'
        with self.assertRaises(ValueError): validate(self.m)
    def test_invalid_references(self):
        for collection,field in [('edges','target'),('nodes','lane'),('lanes','pool')]:
            with self.subTest(collection=collection):
                m=copy.deepcopy(MODEL); m[collection][0][field]='missing'
                with self.assertRaises(ValueError): validate(m)
    def test_invalid_confidence(self):
        for value in [float('nan'), -1, 2, True]:
            self.m['nodes'][0]['confidence']=value
            with self.assertRaises(ValueError): validate(self.m)
    def test_escape(self):
        self.m['nodes'][0]['label']='"]\n click v0 <script>|'
        text=render(self.m)
        self.assertNotIn('<script>',text)
        self.assertNotIn('\n click',text)
        self.assertIn('#34;',text)
    def test_types(self):
        for kind in KINDS:
            self.m['nodes'][0]['kind']=kind
            self.assertTrue(render(self.m).startswith('flowchart LR'))
    def test_edges(self):
        for kind,symbol in [('message','-.->'),('association','-.-')]:
            self.m['edges'][0]['kind']=kind
            self.assertIn(symbol,render(self.m))
    def test_review(self):
        self.m['nodes'][0]['confidence']=.1; self.m['edges']=[]
        self.assertTrue(any('Confiance faible' in x for x in review(self.m)))
        self.assertTrue(any('isolé' in x for x in review(self.m)))
    def test_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('sys.argv',['cmd',str(Path(__file__).parents[1]/'examples/model.json'),'--from-json','-o',tmp]): self.assertEqual(main(),0)
            self.assertEqual((Path(tmp)/'diagram.mmd').read_text(),render(MODEL))
    def test_image(self):
        with self.assertRaises(ValueError): extract(b'bad',model='test')
    def test_http(self):
        received=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append((self.path,json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                self.send_response(200); self.end_headers()
                self.wfile.write(json.dumps({'message':{'content':json.dumps(MODEL)}}).encode())
            def log_message(self,*args): pass
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            self.assertEqual(extract(b'\x89PNG\r\n\x1a\nfixture',model='test',endpoint=f'http://127.0.0.1:{server.server_port}'),MODEL)
            self.assertEqual(received[0][0],'/api/chat')
            self.assertTrue(received[0][1]['messages'][0]['images'])
        finally:
            server.shutdown(); server.server_close(); thread.join()
