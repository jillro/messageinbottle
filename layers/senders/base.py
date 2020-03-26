from typing import Optional

import layers.messages


class BaseSender:
    def send_message(
        self,
        message: layers.messages.SentMessage,
        markdown: bool = False,
        buttons: Optional[list] = None,
    ) -> (str, dict):
        raise NotImplementedError
