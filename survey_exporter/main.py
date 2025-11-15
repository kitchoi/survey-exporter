import pathlib
import queue as _queue
from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict
import contextvars
from contextlib import contextmanager


# module-level contextvar to hold an optional output queue
_out_queue_var: contextvars.ContextVar[Optional[_queue.Queue]] = contextvars.ContextVar(
    "_out_queue_var", default=None
)


@contextmanager
def use_out_queue(q: Optional[_queue.Queue]):
    """
    Context manager to set the module-level out_queue contextvar for the duration
    of the context. Usage:
        with use_out_queue(my_queue):
            build_survey_responses_html(...)
    """
    token = _out_queue_var.set(q)
    try:
        yield
    finally:
        _out_queue_var.reset(token)


# module-level emit helper --- will use the contextvar
def emit(msg: str) -> None:
    """
    Emit a message via the module-level out_queue contextvar if set,
    otherwise print to stdout.
    """
    q = _out_queue_var.get()
    if q is not None:
        try:
            q.put(msg)
            return
        except Exception:
            pass
    print(msg)


@dataclass(frozen=True)
class Entry:
    """Represents a single survey response entry.

    Attributes:
        breaches: List of breach descriptions reported in the survey response.
        date: Date string associated with the survey response.
        time: Time string associated with the survey response.
        media_map: Dictionary mapping cleaned media filenames (suffixes) to their
            original URLs. The keys are cleaned filenames extracted via media_suffix(),
            and values are the full original URLs for downloading.
    """

    breaches: list[str]
    date: str
    time: str
    # mapping from cleaned suffix -> original URL
    media_map: dict[str, str] = field(default_factory=dict)


def media_suffix(url: str) -> str:
    """Extract a cleaned filename suffix from a media URL.

    If the URL contains 'private/', returns everything after that segment.
    Otherwise, returns the last path segment of the URL.

    Args:
        url: The media URL to extract the suffix from.

    Returns:
        The cleaned filename suffix extracted from the URL.

    Examples:
        >>> media_suffix("https://example.com/private/image.jpg")
        "image.jpg"
        >>> media_suffix("https://example.com/files/document.pdf")
        "document.pdf"
    """
    import urllib.parse

    if "private/" in url:
        return url.split("private/", 1)[1]
    else:
        parsed = urllib.parse.urlparse(url)
        return parsed.path.rsplit("/", 1)[-1]


def http_get_head_or_download(
    url: str, headers: dict, target_path: pathlib.Path
) -> bool:
    """Download a file from a URL to a target path with atomic write semantics.

    Creates the target directory if it doesn't exist. Only writes the file if
    the download succeeds. Cleans up any partially written files on failure.

    Args:
        url: The URL to download from.
        headers: Dictionary of HTTP headers to include in the request.
        target_path: Path where the downloaded file should be saved.

    Returns:
        True if the download succeeded and the file was written, False otherwise.

    Note:
        This function implements atomic write semantics - the file is only created
        if the download completes successfully. Any partial files are removed on error.
    """
    import urllib.request

    target_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            # write only if we got data (and no exception)
            with open(target_path, "wb") as f:
                f.write(data)
        return True
    except Exception:
        # cleanup any partially created file
        try:
            if target_path.exists():
                target_path.unlink()
        except Exception:
            pass
        return False


def get_entries(
    api_key: str,
    survey_id: str,
    breaches_id: str,
    date_id: str,
    time_id: str,
    media_url_id: str,
) -> list[Entry]:
    """Fetch survey responses from the Formbricks Management API.

    Retrieves survey responses for the specified survey and field IDs, parsing
    each response into an Entry object. For each entry, constructs a media_map
    dictionary mapping cleaned filenames (via media_suffix) to their original URLs.

    Args:
        api_key: Formbricks API key for authentication (passed in x-api-key header).
        survey_id: The survey ID to fetch responses from.
        breaches_id: Field ID for the breaches field in the survey.
        date_id: Field ID for the date field in the survey.
        time_id: Field ID for the time field in the survey.
        media_url_id: Field ID for the media URL field in the survey.

    Returns:
        List of Entry objects representing the survey responses. Returns an empty
        list if the response data is invalid or not in the expected format.

    Raises:
        RuntimeError: If the HTTP request fails or JSON parsing fails, wrapping
            the underlying exception with a "Failed to fetch entries" message.
        ValueError: If duplicate media suffixes are detected (two different URLs
            would map to the same cleaned filename).
    """
    import json
    import urllib.request
    import urllib.parse
    from typing import Optional

    def http_get_json(url: str, headers: dict) -> Any:
        req = urllib.request.Request(
            url, headers={**headers, "Accept": "application/json"}, method="GET"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)

    def get_value(obj: Any, target: str) -> Optional[Any]:
        return (
            obj["data"][target]
            if isinstance(obj, dict) and "data" in obj and target in obj["data"]
            else None
        )

    headers = {"x-api-key": api_key}
    base_url = f"https://app.formbricks.com/api/v1/management/responses?surveyId={urllib.parse.quote(survey_id)}"

    try:
        payload = http_get_json(base_url, headers)
    except Exception as e:
        # propagate error so callers/tests can observe the failure
        raise RuntimeError(f"Failed to fetch entries: {e}") from e

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []

    entries: list[Entry] = []
    for item in data:
        breaches_val = get_value(item, breaches_id)
        date_val = get_value(item, date_id)
        time_val = get_value(item, time_id)
        media_val = get_value(item, media_url_id)

        media_val = (
            media_val
            if isinstance(media_val, list)
            else [media_val]
            if isinstance(media_val, str)
            else []
        )

        date_str = "" if date_val is None else str(date_val)
        time_str = "" if time_val is None else str(time_val)

        # Clean media URLs using media_suffix and build suffix -> URL map
        media_map: Dict[str, str] = {}
        for url in media_val:
            if not isinstance(url, str):
                continue
            suffix = media_suffix(url)
            if suffix in media_map:
                raise ValueError(
                    f"Duplicate media suffix '{suffix}': first URL '{media_map[suffix]}', "
                    f"current URL '{url}'. Please resolve the naming conflict."
                )
            media_map[suffix] = url

        # create Entry without media attributes, attach media_map dynamically
        entry = Entry(
            breaches=breaches_val if isinstance(breaches_val, list) else [],
            date=date_str,
            time=time_str,
            media_map=media_map,
        )
        entries.append(entry)

    return entries


def build_survey_responses_html(
    api_key: str,
    output_dir: pathlib.Path,
    survey_id: str = "cm5sb0baq0009ms03eli9nlgd",
    breaches_id: str = "e8p6wqvz5ihqls9i1fyy6y1a",
    date_id: str = "h6fzgacr725cmapuwzz9ot5h",
    time_id: str = "o45q50hpyzow5xfgk5dr8ey5",
    media_url_id: str = "qu3bazylkalup4hy24q2pb1n",
) -> str:
    """Build an HTML report of survey responses with downloaded media files.

    Fetches survey responses from the Formbricks Management API, downloads all
    associated media files to a local media subdirectory, and generates an HTML
    table displaying the responses with links to the downloaded media.

    The function handles errors gracefully by writing minimal error HTML when
    the API request fails or no data is found.

    Args:
        api_key: Formbricks API key for authentication.
        output_dir: Directory where the HTML file and media subdirectory will be created.
        survey_id: The survey ID to fetch responses from. Defaults to a specific survey.
        breaches_id: Field ID for the breaches field. Defaults to a specific field.
        date_id: Field ID for the date field. Defaults to a specific field.
        time_id: Field ID for the time field. Defaults to a specific field.
        media_url_id: Field ID for the media URL field. Defaults to a specific field.

    Returns:
        The absolute path to the generated HTML file as a string.

    Note:
        - Creates output_dir and output_dir/media directories if they don't exist.
        - Downloads media files with their cleaned filenames (suffix after 'private/').
        - Implements path traversal protection by sanitizing media filenames.
        - Generates survey_responses.html in the output directory.
        - On API errors, creates a minimal error HTML file and returns its path.
    """
    import urllib.parse

    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / "survey_responses.html"

    # obtain entries via get_entries (keeps concerns separated)
    try:
        entries = get_entries(
            api_key=api_key,
            survey_id=survey_id,
            breaches_id=breaches_id,
            date_id=date_id,
            time_id=time_id,
            media_url_id=media_url_id,
        )
    except RuntimeError as e:
        emit(str(e))
        error_html = f"<html><body><p>Error fetching responses: {e}</p></body></html>"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(error_html)
        return str(html_path)

    if not entries:
        emit("No response data found or unexpected response shape")
        no_data_html = "<html><body><p>No response data found</p></body></html>"
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(no_data_html)
        return str(html_path)

    # Download media files using media_map if present
    headers = {"x-api-key": api_key}
    media_dir = output_dir / "media"
    for entry in entries:
        if not entry.media_map:
            continue
        for suffix, url in entry.media_map.items():
            # Sanitize suffix to prevent path traversal
            safe_suffix = pathlib.Path(suffix).name  # Extract only the filename
            if not safe_suffix or safe_suffix in (".", ".."):
                emit(f"Skipping invalid media filename: {suffix}")
                continue

            target_path = media_dir / safe_suffix
            if target_path.exists():
                emit(f"Media file already exists, skipping download: {target_path}")
                continue

            emit(f"Downloading media: {url} -> {target_path}")
            if not http_get_head_or_download(url, headers, target_path):
                emit(f"Warning: Failed to download {url} -> {target_path}")

    rows: List[str] = []
    for idx, entry in enumerate(entries, start=1):
        emit(f"Processing entry {idx}/{len(entries)}")

        # escape minimal HTML special chars
        def esc(s: str) -> str:
            return (
                s.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&#39;")
            )

        def to_link(s: str) -> str:
            escaped_filename = esc(urllib.parse.unquote(s))
            return f'<a href="media/{esc(s)}">{escaped_filename}</a>'

        breaches_str = "<br/>".join(esc(x) for x in entry.breaches)
        media_str = "<br/>".join(to_link(x) for x in entry.media_map)
        row_html = (
            "<tr>"
            f"<td>{breaches_str}</td>"
            f"<td>{esc(entry.date)}</td>"
            f"<td>{esc(entry.time)}</td>"
            f"<td>{media_str}</td>"
            "</tr>"
        )
        rows.append(row_html)

    table_html = (
        "<table border='1'>"
        "<thead><tr><th>Breaches</th><th>Date</th><th>Time</th><th>Media</th></tr></thead>"
        "<tbody>" + "".join(rows) + "</tbody></table>"
    )
    full_html = f"<!doctype html><html><head><meta charset='utf-8'><title>Survey Responses</title></head><body>{table_html}</body></html>"

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(full_html)
    emit("Done. Output written to survey_responses.html")
    return str(html_path)


if __name__ == "__main__":
    import os
    import sys

    api_key = os.environ.get("SURVEY_API_KEY")
    if not api_key:
        print("Environment variable SURVEY_API_KEY not set", file=sys.stderr)
        sys.exit(2)

    out_dir = pathlib.Path.cwd() / "output"
    build_survey_responses_html(api_key, out_dir)
