"""Explicit scientific rejection; programming errors must not masquerade as one."""


class ScientificRejection(ValueError):
    def __init__(self, reason, status='POSITION_NOT_IDENTIFIABLE'):
        super().__init__(reason)
        self.status = status
