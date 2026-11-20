"""Pelican settings for the blog (R17-R21).

Pelican builds only the blog: content/blog/*.md to _build/blog. The other pages are
hand-written. Page links in the theme are root-absolute (/blog/...), so SITEURL is used
only for the Atom feed's absolute links.
"""

AUTHOR = "Dusten Harrison"
SITENAME = "Bearing Quest"
SITEURL = "https://bearingquest.com/blog"
RELATIVE_URLS = False

PATH = "content"
ARTICLE_PATHS = ["blog"]
PAGE_PATHS = []
STATIC_PATHS = []
OUTPUT_PATH = "_build/blog"

THEME = "theme"
THEME_STATIC_PATHS = []
PLUGINS = []
PLUGIN_PATHS = []

TIMEZONE = "America/Chicago"
DEFAULT_LANG = "en"

ARTICLE_URL = "{slug}.html"
ARTICLE_SAVE_AS = "{slug}.html"
INDEX_SAVE_AS = "index.html"
DIRECT_TEMPLATES = ["index"]

# One Atom feed and nothing else: no author, category, tag, archive, page or
# translation output.
FEED_ALL_ATOM = "feed.xml"
FEED_ALL_RSS = None
CATEGORY_FEED_ATOM = None
CATEGORY_FEED_RSS = None
AUTHOR_FEED_ATOM = None
AUTHOR_FEED_RSS = None
TRANSLATION_FEED_ATOM = None
TRANSLATION_FEED_RSS = None
AUTHOR_SAVE_AS = ""
AUTHORS_SAVE_AS = ""
CATEGORY_SAVE_AS = ""
CATEGORIES_SAVE_AS = ""
TAG_SAVE_AS = ""
TAGS_SAVE_AS = ""
ARCHIVES_SAVE_AS = ""
YEAR_ARCHIVE_SAVE_AS = ""
MONTH_ARCHIVE_SAVE_AS = ""
DAY_ARCHIVE_SAVE_AS = ""
PAGE_SAVE_AS = ""
PAGE_URL = ""
ARTICLE_TRANSLATION_ID = None
ARTICLE_LANG_SAVE_AS = ""
ARTICLE_LANG_URL = ""
DRAFT_SAVE_AS = ""
DRAFT_LANG_SAVE_AS = ""
DRAFT_PAGE_SAVE_AS = ""
DRAFT_PAGE_LANG_SAVE_AS = ""

# Escape every {{ }} in the templates; only the rendered article body is marked safe.
JINJA_ENVIRONMENT = {
    "trim_blocks": True,
    "lstrip_blocks": True,
    "extensions": [],
    "autoescape": True,
}
