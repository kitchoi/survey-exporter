import pathlib
import pytest
from unittest.mock import patch, MagicMock
from survey_exporter.main import (
    Entry,
    build_survey_responses_html,
    get_entries,
    http_get_head_or_download,
)
import json


@pytest.fixture
def mock_api_response():
    return {
        "data": [
            {
                "data": {
                    "breach_123": ["Breach A", "Breach B"],
                    "date_456": "2025-11-15",
                    "time_789": "14:30",
                    "media_101": [
                        "https://example.com/private/file1.pdf",
                        "https://example.com/private/file2.jpg",
                    ],
                }
            },
            {
                "data": {
                    "breach_123": ["Breach C"],
                    "date_456": "2025-11-14",
                    "time_789": "10:15",
                    "media_101": ["https://example.com/uploads/document.png"],
                }
            },
        ]
    }


def test_get_entries_returns_list_of_entries(mock_api_response):
    """Test that get_entries returns a list of Entry objects."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            mock_api_response
        ).encode()
        mock_urlopen.return_value = mock_response

        entries = get_entries(
            api_key="test_key",
            survey_id="survey_123",
            breaches_id="breach_123",
            date_id="date_456",
            time_id="time_789",
            media_url_id="media_101",
        )

        assert isinstance(entries, list)
        assert len(entries) == 2
        assert all(isinstance(entry, Entry) for entry in entries)
        # media_map should be present on entries (may be empty dict)
        assert isinstance(entries[0].media_map, dict)


def test_get_entries_populates_entry_fields(mock_api_response):
    """Test that Entry objects are populated with correct values."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            mock_api_response
        ).encode()
        mock_urlopen.return_value = mock_response

        entries = get_entries(
            api_key="test_key",
            survey_id="survey_123",
            breaches_id="breach_123",
            date_id="date_456",
            time_id="time_789",
            media_url_id="media_101",
        )

        entry = entries[0]
        assert entry.breaches == ["Breach A", "Breach B"]
        assert entry.date == "2025-11-15"
        assert entry.time == "14:30"
        # media_map should contain cleaned suffix keys mapping to original URLs
        assert "file1.pdf" in entry.media_map
        assert entry.media_map["file1.pdf"] == "https://example.com/private/file1.pdf"
        assert "file2.jpg" in entry.media_map
        assert entry.media_map["file2.jpg"] == "https://example.com/private/file2.jpg"
        # second entry media_map contains document.png
        assert "document.png" in entries[1].media_map
        assert (
            entries[1].media_map["document.png"]
            == "https://example.com/uploads/document.png"
        )


def test_get_entries_cleans_media_urls_with_private_suffix():
    """Test that media URLs are cleaned using media_suffix function."""
    response = {
        "data": [
            {
                "data": {
                    "breach_123": [],
                    "date_456": "2025-11-15",
                    "time_789": "14:30",
                    "media_101": ["https://example.com/private/cleaned_file.pdf"],
                }
            }
        ]
    }
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            response
        ).encode()
        mock_urlopen.return_value = mock_response

        entries = get_entries(
            api_key="test_key",
            survey_id="survey_123",
            breaches_id="breach_123",
            date_id="date_456",
            time_id="time_789",
            media_url_id="media_101",
        )

        assert "cleaned_file.pdf" in entries[0].media_map
        assert (
            entries[0].media_map["cleaned_file.pdf"]
            == "https://example.com/private/cleaned_file.pdf"
        )


def test_get_entries_cleans_media_urls_without_private_suffix():
    """Test that media URLs without 'private/' are cleaned to last path segment."""
    response = {
        "data": [
            {
                "data": {
                    "breach_123": [],
                    "date_456": "2025-11-15",
                    "time_789": "14:30",
                    "media_101": ["https://example.com/uploads/document.png"],
                }
            }
        ]
    }
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            response
        ).encode()
        mock_urlopen.return_value = mock_response

        entries = get_entries(
            api_key="test_key",
            survey_id="survey_123",
            breaches_id="breach_123",
            date_id="date_456",
            time_id="time_789",
            media_url_id="media_101",
        )

        assert "document.png" in entries[0].media_map
        assert (
            entries[0].media_map["document.png"]
            == "https://example.com/uploads/document.png"
        )


def test_get_entries_handles_missing_fields():
    """Test that get_entries handles missing fields gracefully."""
    response = {"data": [{"data": {"breach_123": []}}]}

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            response
        ).encode()
        mock_urlopen.return_value = mock_response

        entries = get_entries(
            api_key="test_key",
            survey_id="survey_123",
            breaches_id="breach_123",
            date_id="date_456",
            time_id="time_789",
            media_url_id="media_101",
        )

        entry = entries[0]
        assert entry.breaches == []
        assert entry.date == ""
        assert entry.time == ""
        # no media -> empty mapping
        assert entry.media_map == {}


def test_get_entries_handles_single_media_url():
    """Test that a single media URL string is converted to a mapping entry."""
    response = {
        "data": [
            {
                "data": {
                    "breach_123": [],
                    "date_456": "2025-11-15",
                    "time_789": "14:30",
                    "media_101": "https://example.com/private/single_file.pdf",
                }
            }
        ]
    }
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            response
        ).encode()
        mock_urlopen.return_value = mock_response

        entries = get_entries(
            api_key="test_key",
            survey_id="survey_123",
            breaches_id="breach_123",
            date_id="date_456",
            time_id="time_789",
            media_url_id="media_101",
        )

        assert "single_file.pdf" in entries[0].media_map
        assert (
            entries[0].media_map["single_file.pdf"]
            == "https://example.com/private/single_file.pdf"
        )


def test_get_entries_returns_empty_list_on_invalid_response():
    """Test that get_entries returns empty list if response data is not a list."""
    response = {"data": "invalid"}

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            response
        ).encode()
        mock_urlopen.return_value = mock_response

        entries = get_entries(
            api_key="test_key",
            survey_id="survey_123",
            breaches_id="breach_123",
            date_id="date_456",
            time_id="time_789",
            media_url_id="media_101",
        )

        assert entries == []


def test_get_entries_raises_on_http_error():
    """If the HTTP/JSON fetch fails, get_entries should raise a RuntimeError with a message."""
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = Exception("network failure")

        with pytest.raises(RuntimeError) as excinfo:
            get_entries(
                api_key="test_key",
                survey_id="survey_123",
                breaches_id="breach_123",
                date_id="date_456",
                time_id="time_789",
                media_url_id="media_101",
            )

        assert "Failed to fetch entries" in str(excinfo.value)


def test_get_entries_raises_on_duplicate_media_suffix():
    """Test that get_entries raises ValueError when media URLs produce duplicate suffixes."""
    response = {
        "data": [
            {
                "data": {
                    "breach_123": [],
                    "date_456": "2025-11-15",
                    "time_789": "14:30",
                    "media_101": [
                        "https://example.com/private/document.pdf",
                        "https://other.com/private/document.pdf",
                    ],
                }
            }
        ]
    }

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.__enter__.return_value.read.return_value = json.dumps(
            response
        ).encode()
        mock_urlopen.return_value = mock_response

        with pytest.raises(ValueError) as excinfo:
            get_entries(
                api_key="test_key",
                survey_id="survey_123",
                breaches_id="breach_123",
                date_id="date_456",
                time_id="time_789",
                media_url_id="media_101",
            )

        error_msg = str(excinfo.value)
        assert "Duplicate media suffix" in error_msg
        assert "document.pdf" in error_msg
        assert "https://example.com/private/document.pdf" in error_msg
        assert "https://other.com/private/document.pdf" in error_msg
        assert "naming conflict" in error_msg


def make_filelike_with_read(content):
    m = MagicMock()
    # json.load expects a text file-like (returning str)
    m.read.return_value = content
    return m


def test_build_survey_responses_html_downloads_media(tmp_path):
    """Test that build_survey_responses_html downloads media files to output_dir/media."""
    api_payload = {
        "data": [
            {
                "data": {
                    "breach_123": ["Breach A"],
                    "date_456": "2025-11-15",
                    "time_789": "14:30",
                    "media_101": [
                        "https://example.com/private/file1.jpg",
                        "https://example.com/uploads/doc.pdf",
                    ],
                }
            }
        ]
    }

    # prepare the sequence of urlopen returns:
    # 1) JSON response (returning str)
    # 2) download file1.jpg (returning bytes)
    # 3) download doc.pdf (returning bytes)
    json_filelike = make_filelike_with_read(json.dumps(api_payload))
    file1_bytes = make_filelike_with_read(b"file1-binary")
    file2_bytes = make_filelike_with_read(b"file2-binary")

    ctx_json = MagicMock()
    ctx_json.__enter__.return_value = json_filelike
    ctx_file1 = MagicMock()
    ctx_file1.__enter__.return_value = file1_bytes
    ctx_file2 = MagicMock()
    ctx_file2.__enter__.return_value = file2_bytes

    with patch(
        "urllib.request.urlopen", side_effect=[ctx_json, ctx_file1, ctx_file2]
    ) as mock_urlopen:
        out = build_survey_responses_html(
            api_key="test_key",
            output_dir=pathlib.Path(tmp_path),
            survey_id="survey_123",
            breaches_id="breach_123",
            date_id="date_456",
            time_id="time_789",
            media_url_id="media_101",
        )

        # expect two downloads + one json fetch -> 3 calls
        assert mock_urlopen.call_count == 3

        media_dir = pathlib.Path(tmp_path) / "media"
        file1_path = media_dir / "file1.jpg"
        file2_path = media_dir / "doc.pdf"

        assert file1_path.exists()
        assert file1_path.read_bytes() == b"file1-binary"
        assert file2_path.exists()
        assert file2_path.read_bytes() == b"file2-binary"

        # HTML output file created and contains media_map keys (filenames)
        html_path = pathlib.Path(out)
        assert html_path.exists()
        html_text = html_path.read_text(encoding="utf-8")
        assert "file1.jpg" in html_text
        assert "doc.pdf" in html_text


def test_http_get_head_or_download_cleans_up_on_failure(tmp_path):
    """Test that http_get_head_or_download removes partial files on download failure."""
    target_path = tmp_path / "failed_download.pdf"

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_urlopen.side_effect = Exception("network error")

        result = http_get_head_or_download(
            url="https://example.com/private/file.pdf",
            headers={"x-api-key": "test_key"},
            target_path=target_path,
        )

        # Should return False on failure
        assert result is False
        # File should not exist
        assert not target_path.exists()
