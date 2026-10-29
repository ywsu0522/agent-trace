"""Historical comparison metric: ceil(characters / 4), plus 4 per message.

This deterministic estimate preserves the archived study's units. It is not
Ollama's tokenizer, context measurement, or an estimate of model attention.
"""


def count_tokens(text):
    return (len(text) + 3) // 4


def count_message_tokens(messages):
    return sum(count_tokens(message['content']) + 4 for message in messages)
