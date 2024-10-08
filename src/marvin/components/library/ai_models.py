import json
from typing import Optional

import httpx
from pydantic import BaseModel
from typing_extensions import Self

from marvin import ai_model
from marvin._compat import Field, SecretStr, field_validator
from marvin.settings import MarvinBaseSettings


class DiscourseSettings(MarvinBaseSettings):
    class Config:
        env_prefix = "MARVIN_DISCOURSE_"

    help_category_id: Optional[int] = Field(
        None, env=["MARVIN_DISCOURSE_HELP_CATEGORY_ID"]
    )
    api_key: Optional[SecretStr] = Field(None, env=["MARVIN_DISCOURSE_API_KEY"])
    api_username: Optional[str] = Field(None, env=["MARVIN_DISCOURSE_API_USERNAME"])
    url: Optional[str] = Field(None, env=["MARVIN_DISCOURSE_URL"])


discourse_settings = DiscourseSettings()


@ai_model(instructions="Produce a comprehensive Discourse post from text.")
class DiscoursePost(BaseModel):
    title: Optional[str] = Field(
        description="A fitting title for the post.",
        example="How to install Prefect",
    )
    question: Optional[str] = Field(
        description="The question that is posed in the text.",
        example="How do I install Prefect?",
    )
    answer: Optional[str] = Field(
        description=(
            "The complete answer to the question posed in the text."
            " This answer should comprehensively answer the question, "
            " explain any relevant concepts, and have a friendly, academic tone,"
            " and provide any links to relevant resources found in the thread."
            " This answer should be written in Markdown, with any code blocks"
            " formatted as `code` or ```<language_name>\n<the code block itself>```."
        )
    )

    topic_url: Optional[str] = Field(None)

    @field_validator("title", "question", "answer")
    def non_empty_string(cls, value):
        if not value:
            raise ValueError("this field cannot be empty")
        return value

    @classmethod
    def from_slack_thread(cls, messages: list[str]) -> Self:
        return cls("here is the transcript:\n" + "\n\n".join(messages))

    async def publish(
        self,
        topic: str = None,
        category: Optional[int] = None,
        url: str = discourse_settings.url,
        tags: list[str] = None,
    ) -> str:
        if not category:
            category = discourse_settings.help_category_id

        headers = {
            "Api-Key": discourse_settings.api_key.get_secret_value(),
            "Api-Username": discourse_settings.api_username,
            "Content-Type": "application/json",
        }
        data = {
            "title": self.title,
            "raw": (
                f"## **{self.question}**\n\n{self.answer}"
                "\n\n---\n\n*This topic was created by Marvin.*"
            ),
            "category": category,
            "tags": tags or ["marvin"],
        }

        if topic:
            data["tags"].append(topic)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url=f"{url}/posts.json", headers=headers, data=json.dumps(data)
            )

        response.raise_for_status()

        response_data = response.json()
        topic_id = response_data.get("topic_id")
        post_number = response_data.get("post_number")

        self.topic_url = f"{url}/t/{topic_id}/{post_number}"

        return self.topic_url
