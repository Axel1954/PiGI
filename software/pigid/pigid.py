import os
import logging
import json

import bottle
from gevent.pywsgi import WSGIServer
from geventwebsocket import WebSocketHandler, WebSocketError

try:
    import config
except:
    print "Could not import config file."
    print "Copy config.py.EXAMPLE to config.py and adapt it for your setup."
    exit(1)

logging.basicConfig(level=config.log_level, format=config.log_format)
log = logging.getLogger("pigid")
log.info("Starting pigid")

app = bottle.Bottle()


script_dir = os.path.dirname(os.path.realpath(__file__))

@app.route('/')
def index():
    return bottle.redirect('/pigi/index.html')


@app.route('/pigi/:filename#.*#')
def send_static(filename):
    log.debug("serving %s" % filename)
    return bottle.static_file(filename, root='./public/')


def get_websocket_from_request():
    env = bottle.request.environ
    wsock = env.get('wsgi.websocket')
    if not wsock:
        abort(400, 'Expected WebSocket request.')
    return wsock


@app.route('/ws')
def handle_ws():
    wsock = get_websocket_from_request()
    log.info("websocket opened")
    while True:
        try:
            message = wsock.receive()
            log.info("Received : %s" % message)
            msgdict = json.loads(message)
            
        except WebSocketError:
            break
    log.info("websocket (control) closed")


def main():
    ip = config.listening_ip
    port = config.listening_port
    log.info("listening on %s:%d" % (ip, port))

    server = WSGIServer((ip, port), app,
                        handler_class=WebSocketHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()