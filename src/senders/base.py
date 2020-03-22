from typing import Optional

import models


class BaseSender:
    def send_message(
        self,
        message: models.SentMessage,
        markdown: bool = False,
        buttons: Optional[list] = None,
    ) -> (str, dict):
        raise NotImplementedError
