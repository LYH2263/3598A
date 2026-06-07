import logging
import re
import string

from notices.models import MessageTemplate, MessageType

logger = logging.getLogger(__name__)


class TemplateEngine:
    _PLACEHOLDER_RE = re.compile(r'\{(\w+)\}')

    @classmethod
    def render(cls, template: MessageTemplate, variables: dict) -> tuple[str, str]:
        title = cls._format_safe(template.title_template, variables)
        content = cls._format_safe(template.content_template, variables)
        return title, content

    @classmethod
    def _format_safe(cls, template_str: str, variables: dict) -> str:
        try:
            formatter = string.Formatter()
            return formatter.vformat(template_str, (), variables or {})
        except (KeyError, IndexError, ValueError) as e:
            logger.warning('Template render failed, falling back to raw replacement: %s', e)
            return cls._fallback_render(template_str, variables or {})

    @classmethod
    def _fallback_render(cls, template_str: str, variables: dict) -> str:
        def replacer(match):
            key = match.group(1)
            return str(variables.get(key, match.group(0)))
        return cls._PLACEHOLDER_RE.sub(replacer, template_str)

    @classmethod
    def validate_template(cls, template_str: str) -> list[str]:
        placeholders = cls._PLACEHOLDER_RE.findall(template_str)
        return placeholders

    @classmethod
    def get_template_for_language(cls, message_type: MessageType, language: str) -> MessageTemplate | None:
        templates = {t.language: t for t in message_type.templates.filter(is_active=True)}
        if language in templates:
            return templates[language]
        if MessageTemplate.LANG_ZH in templates:
            return templates[MessageTemplate.LANG_ZH]
        return next(iter(templates.values()), None) if templates else None
