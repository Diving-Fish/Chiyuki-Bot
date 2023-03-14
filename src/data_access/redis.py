import redis

redis_global = redis.Redis(host='localhost', port=6379, decode_responses=True)  