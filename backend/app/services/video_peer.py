"""Optional authorized receiver coordination. Only predefined video operations."""
import asyncio,json,urllib.request
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
class VideoPeer:
    def __init__(self,url,token):self.url=url;self.token=token
    async def call(self,path,body=None):
        def request():
            req=urllib.request.Request(self.url+'/api/video/peer/'+path,data=json.dumps(body).encode() if body is not None else None,
                headers={'Authorization':'Bearer '+self.token,'Content-Type':'application/json'})
            with urllib.request.build_opener(NoRedirect).open(req,timeout=15) as response:
                data=response.read(5*1024*1024+1)
                if len(data)>5*1024*1024:raise ValueError('Peer response exceeds limit')
                return json.loads(data)
        return await asyncio.to_thread(request)
