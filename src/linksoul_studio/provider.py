"""Minimal server-side Ollama text provider; no tools, skills or motion dispatch."""
import json
import time
import urllib.request
from urllib.parse import urlsplit


class ProviderError(Exception):
    pass


class TextProvider:
    def __init__(self, settings):
        self.settings = settings

    @property
    def issue(self):
        s = self.settings
        if s.reply_provider == 'disabled':
            return 'Reply provider disabled. Configure STUDIO_REPLY_PROVIDER=ollama, OLLAMA_URL and OLLAMA_MODEL on the server.'
        try:
            u = urlsplit(s.ollama_url)
            valid_url = u.scheme in {'http','https'} and u.hostname and not any((u.username,u.password,u.query,u.fragment))
        except ValueError:
            valid_url = False
        if s.reply_provider != 'ollama' or not 0 < len(s.ollama_model) <= 128 or len(s.ollama_url)>2048 or not valid_url:
            return 'Invalid reply provider configuration. Set an Ollama server URL and installed model, then recreate.'
        return None

    def reply(self, text):
        if self.issue:
            raise ProviderError(self.issue)
        s = self.settings
        payload = json.dumps({'model':s.ollama_model,'stream':False,'messages':[
            {'role':'system','content':'Reply briefly in plain text. You cannot operate the robot; never claim to have performed an action.'},
            {'role':'user','content':text}], 'options':{'num_predict':512}}).encode()
        req = urllib.request.Request(s.ollama_url.rstrip('/')+'/api/chat',data=payload,headers={'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=20) as response:
                deadline = time.monotonic()+20
                chunks=[]
                size=0
                while size<=131072:
                    if time.monotonic()>deadline:
                        raise ValueError
                    chunk=response.read1(min(16384,131073-size))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size+=len(chunk)
                raw=b''.join(chunks)
            if len(raw)>131072:
                raise ValueError
            data=json.loads(raw)
            result=data['message']['content']
            if data.get('done') is not True or not isinstance(result,str) or not result.strip() or len(result)>s.max_text:
                raise ValueError
            return result
        except Exception:
            # Do not expose URLs, provider bodies, exceptions or request text.
            raise ProviderError('Reply provider failed or timed out. Check Ollama availability, model and response size; retry with a new interaction.') from None
