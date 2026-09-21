bind = "0.0.0.0:8000"
# gthread: uploads lentos (send_file de vídeo, chamadas à Meta) seguram só uma thread,
# não o worker inteiro. Poucos processos porque o container tem limite de 768 MB.
workers = 3
threads = 4
worker_class = "gthread"
timeout = 120
keepalive = 2
accesslog = "-"
errorlog = "-"
loglevel = "info"
# Formato padrão + duração da requisição em microssegundos (%(D)s) para diagnosticar lentidão.
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'
preload_app = True
