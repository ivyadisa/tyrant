from django.core.cache import cache

def is_duplicate(transaction_id):

    if cache.get(transaction_id):
        return True

    cache.set(transaction_id, True, timeout=300)
    return False