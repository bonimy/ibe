from webob import Request
from webob.exc import HTTPBadRequest


class LimitUploadSize(object):

    def __init__(self, app, size):
        self.app = app
        self.size = size

    def __call__(self, environ, start_response):
        req = Request(environ)
        if req.method=='POST':
            len = req.headers.get('Content-length')
            if not len:
                return HTTPBadRequest("No content-length header specified")(environ, start_response)
            elif int(len) > self.size:
                return HTTPBadRequest("POST body exceeds maximum limits - if you were uploading a table, please split into pieces that are smaller than 1MB, and submit a series of queries instead.")(environ, start_response)
        resp = req.get_response(self.app)
        return resp(environ, start_response)

