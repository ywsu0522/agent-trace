"""Local model error contract retained by the migrated agent loop."""


class OutputTruncated(RuntimeError):
    def __init__(self, text=''):
        super().__init__('Model output was truncated')
        self.text = text
