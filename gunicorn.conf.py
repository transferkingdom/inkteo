bind = "0.0.0.0:8000"
workers = 2
timeout = 300  # 5 dakika
max_requests = 1000
max_requests_jitter = 50
preload_app = True
worker_class = "sync"
limit_request_line = 0
limit_request_fields = 32768
limit_request_field_size = 0 