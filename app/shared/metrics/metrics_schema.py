class KafkaMetrics:
    """Standard metric keys for KafkaClient"""
    PRODUCED = "produced"
    FAILED_PRODUCE = "failed_produce"
    DLQ = "dlq"
    PROCESSED = "processed"
    FAILED_PROCESS = "failed_process"


class RedisMetrics:
    """Standard metric keys for RedisClient"""
    SET = "redis_set"
    GET = "redis_get"
    DEL = "redis_del"
    EXISTS = "redis_exists"
    FAILED_SET = "redis_failed_set"
    FAILED_GET = "redis_failed_get"
    FAILED_DEL = "redis_failed_del"
    FAILED_EXISTS = "redis_failed_exists"
