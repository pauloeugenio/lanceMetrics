"""Optional authorized receiver coordination. Only predefined video operations."""
import asyncio,json,urllib.request,urllib.error
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None
class VideoPeer:
    def __init__(self,url,token):self.url=url;self.token=token
    async def call(self,path,body=None):
        def request():
            headers={'Content-Type':'application/json'}
            if self.token:headers['Authorization']='Bearer '+self.token
            req=urllib.request.Request(self.url+'/api/video/peer/'+path,data=json.dumps(body).encode() if body is not None else None,
                headers=headers)
            with urllib.request.build_opener(NoRedirect).open(req,timeout=15) as response:
                data=response.read(5*1024*1024+1)
                if len(data)>5*1024*1024:raise ValueError('Peer response exceeds limit')
                return json.loads(data)
        try:return await asyncio.to_thread(request)
        except urllib.error.HTTPError as ex:
            if ex.code in (401,403):raise ValueError('Client authentication is enabled. Provide the client token or disable authentication on that instance.') from ex
            raise ValueError(f'Client returned HTTP {ex.code}') from ex
        except urllib.error.URLError as ex:raise ValueError(f'Cannot connect to client: {ex.reason}') from ex
