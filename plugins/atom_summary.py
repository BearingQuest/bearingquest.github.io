"""Pelican plugin: each Atom entry carries the summary and no full content (R21).

Pelican 4.12.0 has no setting for this: RSS_FEED_SUMMARY_ONLY covers RSS only, and the
Atom branch of Writer._add_item_to_the_feed always adds the full content. So this module
copies that method from pelican 4.12.0 (pelican/writers.py) and changes the Atom branch.
The copy is only valid for that version, so importing it under any other Pelican raises:
re-check the copy against the new pelican/writers.py, then update EXPECTED_PELICAN.
"""

from __future__ import annotations

from typing import Any

import pelican
from feedgenerator import Rss201rev2Feed, get_tag_uri
from markupsafe import Markup
from pelican.plugins import signals
from pelican.utils import set_date_tzinfo
from pelican.writers import Writer

EXPECTED_PELICAN = "4.12.0"

if pelican.__version__ != EXPECTED_PELICAN:
    raise RuntimeError(
        f"plugins/atom_summary.py copies Writer._add_item_to_the_feed from pelican "
        f"{EXPECTED_PELICAN}, but pelican {pelican.__version__} is installed. Re-check the "
        f"copy against pelican/writers.py, then update EXPECTED_PELICAN."
    )


class SummaryOnlyWriter(Writer):
    """The 4.12.0 writer, with Atom entries limited to the summary."""

    def _add_item_to_the_feed(self, feed: Any, item: Any) -> None:
        # Copied as is: Markup only strips tags from the post's own title, and the feed escapes it.
        title = Markup(item.title).striptags()  # noqa: S704
        link = self.urljoiner(self.site_url, item.url)

        if self.settings["FEED_APPEND_REF"]:
            link = link + "?ref=feed"

        content: str | None
        if isinstance(feed, Rss201rev2Feed):
            content = None
            if self.settings.get("RSS_FEED_SUMMARY_ONLY"):
                description = item.summary
            else:
                description = item.get_content(self.site_url)
        else:
            # Changed from 4.12.0, which sets content = item.get_content(self.site_url).
            content = None
            description = item.summary

        categories = []
        if hasattr(item, "category"):
            categories.append(item.category)
        if hasattr(item, "tags"):
            categories.extend(item.tags)

        feed.add_item(
            title=title,
            link=link,
            unique_id=get_tag_uri(link, item.date),
            description=description,
            content=content,
            categories=categories or None,
            author_name=getattr(item, "author", ""),
            pubdate=set_date_tzinfo(item.date, self.settings.get("TIMEZONE", None)),
            updateddate=set_date_tzinfo(item.modified, self.settings.get("TIMEZONE", None))
            if hasattr(item, "modified")
            else None,
        )


def get_writer(_generators: object) -> type[Writer]:
    return SummaryOnlyWriter


def register() -> None:
    signals.get_writer.connect(get_writer)
