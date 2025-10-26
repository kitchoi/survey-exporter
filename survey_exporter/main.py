from dataclasses import dataclass
import pathlib


@dataclass(frozen=True)
class Entry:
    breaches: list[str]
    date: str
    time: str
    media: dict[str, bytes]


def media_suffix(url: str) -> str:
    """
    Given a media URL, return the suffix after 'private/' if present,
    otherwise return the last path segment.
    """
    import urllib.parse

    if "private/" in url:
        return url.split("private/", 1)[1]
    else:
        parsed = urllib.parse.urlparse(url)
        return parsed.path.rsplit("/", 1)[-1]


def build_survey_responses_html(
    api_key: str,
    output_dir: pathlib.Path,
    survey_id: str = "cm5sb0baq0009ms03eli9nlgd",
    breaches_id: str = "e8p6wqvz5ihqls9i1fyy6y1a",
    date_id: str = "h6fzgacr725cmapuwzz9ot5h",
    time_id: str = "o45q50hpyzow5xfgk5dr8ey5",
    media_url_id: str = "qu3bazylkalup4hy24q2pb1n",
) -> str:
    """
    Fetch survey responses from Formbricks Management API and return an HTML table
    as a single string with columns: Breaches, Date, Time, Media.

    Notes:
    - The function will call the endpoint:
      https://api.formbricks.com/api/management/surveys/{survey_id}/responses
      with header 'x-api-key': api_key
    - For each response entry it will search for attributes whose key matches
      the provided *_id parameters. Media files found at URLs are downloaded
      (request made with same x-api-key header) but not stored; only the suffix
      after 'private/' is retained for the HTML output.
    """
    import json
    import urllib.request
    import urllib.parse
    from typing import Any, Optional, List

    def http_get_json(url: str, headers: dict) -> Any:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req) as resp:
            return json.load(resp)

    def http_get_head_or_download(url: str, headers: dict) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        target_path = output_dir / urllib.parse.unquote(media_suffix(url))
        if target_path.exists():
            return
        print("Downloading media:", url)
        with open(target_path, "wb") as f:
            try:
                req = urllib.request.Request(url, headers=headers, method="GET")
                with urllib.request.urlopen(req) as resp:
                    while (chunk := resp.read(8192)):
                        f.write(chunk)
            except Exception:
                pass


    def get_value(obj: Any, target: str) -> Optional[Any]:
        """
        Recursively search for a key in nested dict/list structures.
        Returns the first matching value found or None.
        """
        return obj["data"][target] if isinstance(obj, dict) and "data" in obj and target in obj["data"] else None

    headers = {"x-api-key": api_key, "Accept": "application/json"}
    base_url = f"https://app.formbricks.com/api/v1/management/responses?surveyId={urllib.parse.quote(survey_id)}"

    # fetch responses
    try:
        payload = http_get_json(base_url, headers)
    except Exception as e:
        # return minimal HTML indicating error
        return f"<html><body><p>Error fetching responses: {str(e)}</p></body></html>"

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        # unexpected shape
        return "<html><body><p>No response data found</p></body></html>"

    rows: List[str] = []
    entries: List[Entry] = []
    for item in data:
        # find breaches (expected list), date (scalar), time (scalar), media (list of urls)
        breaches_val = get_value(item, breaches_id)
        date_val = get_value(item, date_id)
        time_val = get_value(item, time_id)
        media_val = get_value(item, media_url_id)
        media_val = media_val if isinstance(media_val, list) else [media_val] if isinstance(media_val, str) else []

        date_str = "" if date_val is None else str(date_val)
        time_str = "" if time_val is None else str(time_val)
        entries.append(
            Entry(breaches=breaches_val if isinstance(breaches_val, list) else [],
                  date=date_str,
                  time=time_str,
                  media={media_suffix(url): http_get_head_or_download(url, headers) for url in media_val},
            )
        )
    
    for entry in sorted(entries, key=lambda e: (e.date, e.time), reverse=True):
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
            return f'<a href="{s}">{esc(s)}</a>'

        breaches_str = "<br/>".join(esc(x) for x in entry.breaches)
        media_str = "<br/>".join(to_link(x) for x in entry.media)
        row_html = (
            "<tr>"
            f"<td>{breaches_str}</td>"
            f"<td>{esc(entry.date)}</td>"
            f"<td>{esc(entry.time)}</td>"
            f"<td>{media_str}</td>"
            "</tr>"
        )
        rows.append(row_html)
        print("Processed entry:", entry.date, entry.time)

    table_html = (
        "<table border='1'>"
        "<thead><tr><th>Breaches</th><th>Date</th><th>Time</th><th>Media</th></tr></thead>"
        "<tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )
    full_html = f"<!doctype html><html><head><meta charset='utf-8'><title>Survey Responses</title></head><body>{table_html}</body></html>"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "survey_responses.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print("Done. Output written to survey_responses.html")

    


if __name__ == "__main__":
    import sys
    build_survey_responses_html(sys.argv[1], pathlib.Path(sys.argv[2]))
