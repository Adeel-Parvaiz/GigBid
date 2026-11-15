# 0003 Idempotency key = hash(freelancer, job, final text)
Thread-independent, so a replayed/retried/duplicated run cannot submit or spend Connects twice. A changed text is a different proposal (new key) on purpose.
