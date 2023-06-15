"""OpenAI chat wrapper."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from pydantic import Extra, Field, root_validator

from autochain.agent.message import BaseMessage
from autochain.models.base import (
    LLMResult,
    convert_dict_to_message,
    convert_message_to_dict,
    Generation,
    BaseLanguageModel,
)

logger = logging.getLogger(__name__)


class ChatOpenAI(BaseLanguageModel):
    """Wrapper around OpenAI Chat large language models.

    To use, you should have the ``openai`` python package installed, and the
    environment variable ``OPENAI_API_KEY`` set with your API key.

    Any parameters that are valid to be passed to the openai.create call can be passed
    in, even if not explicitly saved on this class.

    Example:
        .. code-block:: python

            from langchain.chat_models import ChatOpenAI
            openai = ChatOpenAI(model_name="gpt-3.5-turbo")
    """

    client: Any  #: :meta private:
    model_name: str = "gpt-3.5-turbo"
    """Model name to use."""
    temperature: float = 0
    """What sampling temperature to use."""
    model_kwargs: Dict[str, Any] = Field(default_factory=dict)
    """Holds any model parameters valid for `create` call not explicitly specified."""
    openai_api_key: Optional[str] = None
    openai_organization: Optional[str] = None
    request_timeout: Optional[Union[float, Tuple[float, float]]] = None
    """Timeout for requests to OpenAI completion API. Default is 600 seconds."""
    max_retries: int = 6
    # TODO: support streaming
    # """Maximum number of retries to make when generating."""
    # streaming: bool = False
    # """Whether to stream the results or not."""
    # n: int = 1
    """Number of chat completions to generate for each prompt."""
    max_tokens: Optional[int] = None
    """Maximum number of tokens to generate."""

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.ignore

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that api key and python package exists in environment."""
        openai_api_key = os.environ["OPENAI_API_KEY"]
        try:
            import openai

        except ImportError:
            raise ValueError(
                "Could not import openai python package. "
                "Please install it with `pip install openai`."
            )
        openai.api_key = openai_api_key
        try:
            values["client"] = openai.ChatCompletion
        except AttributeError:
            raise ValueError(
                "`openai` has no `ChatCompletion` attribute, this is likely "
                "due to an old version of the openai package. Try upgrading it "
                "with `pip install --upgrade openai`."
            )
        # if values["n"] < 1:
        #     raise ValueError("n must be at least 1.")
        # if values["n"] > 1 and values["streaming"]:
        #     raise ValueError("n must be 1 when streaming.")
        return values

    def generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
    ) -> LLMResult:
        message_dicts, params = self._create_message_dicts(messages, stop)
        response = self.generate_with_retry(messages=message_dicts, **params)
        return self._create_llm_result(response)

    def _create_message_dicts(
        self, messages: List[BaseMessage], stop: Optional[List[str]]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        params: Dict[str, Any] = {**{"model": self.model_name}, **self._default_params}
        if stop is not None:
            if "stop" in params:
                raise ValueError("`stop` found in both the input and default params.")
            params["stop"] = stop
        message_dicts = [convert_message_to_dict(m) for m in messages]
        return message_dicts, params

    def _create_llm_result(self, response: Mapping[str, Any]) -> LLMResult:
        generations = []
        for res in response["choices"]:
            message = convert_dict_to_message(res["message"])
            gen = Generation(message=message)
            generations.append(gen)
        llm_output = {"token_usage": response["usage"], "model_name": self.model_name}
        result = LLMResult(generations=generations, llm_output=llm_output)
        return result