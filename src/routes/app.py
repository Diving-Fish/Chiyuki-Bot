from quart import Quart

YOUR_HOST = 'www.diving-fish.com'

# 创建 Quart 应用实例
quart_app = Quart(__name__)

@quart_app.after_request
def cors(environ):
    environ.headers['Access-Control-Allow-Origin'] = YOUR_HOST
    environ.headers['Access-Control-Allow-Method'] = '*'
    environ.headers['Access-Control-Allow-Headers'] = 'x-requested-with,content-type'
    return environ
