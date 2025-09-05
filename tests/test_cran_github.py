import os
from unittest.mock import MagicMock, patch

import pytest

from grayskull.config import Configuration
from grayskull.strategy.cran import get_github_r_metadata, download_github_r_pkg


@patch("grayskull.strategy.cran.handle_gh_version")
@patch("grayskull.strategy.cran.generate_git_archive_tarball_url")
@patch("grayskull.strategy.cran.download_github_r_pkg")
@patch("grayskull.strategy.cran.get_archive_metadata")
@patch("grayskull.strategy.cran.sha256_checksum")
def test_get_github_r_metadata(
    mock_sha256,
    mock_get_archive_metadata,
    mock_download_github_r_pkg,
    mock_generate_archive_url,
    mock_handle_gh_version,
    tmp_path,
):
    """Test getting metadata for R package from GitHub"""
    
    # Setup mocks
    mock_handle_gh_version.return_value = ("1.0.0", "v1.0.0")
    mock_generate_archive_url.return_value = "https://github.com/user/rpkg/archive/v1.0.0.tar.gz"
    mock_download_github_r_pkg.return_value = str(tmp_path / "rpkg-v1.0.0.tar.gz")
    mock_sha256.return_value = "abc123"
    mock_get_archive_metadata.return_value = {
        "orig_lines": ["Package: rpkg", "Version: 1.0.0", "License: MIT"],
        "Package": "rpkg",
        "Version": "1.0.0",
        "License": "MIT",
        "Description": "A test R package",
        "Imports": "ggplot2, dplyr (>= 1.0.0)",
        "NeedsCompilation": "no",
    }
    
    # Test configuration
    config = Configuration(name="https://github.com/user/rpkg", version="1.0.0")
    
    # Call the function
    result_metadata, r_recipe_comment = get_github_r_metadata(config)
    
    # Verify the result
    assert result_metadata["package"]["name"] == "r-{{ name }}"
    assert result_metadata["package"]["version"] == "{{ version }}"
    assert result_metadata["source"]["url"] == "https://github.com/user/rpkg/archive/{{ version }}.tar.gz"
    assert result_metadata["source"]["sha256"] == "abc123"
    assert result_metadata["about"]["home"] == "https://github.com/user/rpkg"
    assert result_metadata["about"]["dev_url"] == "https://github.com/user/rpkg"
    assert result_metadata["about"]["summary"] == "A test R package"
    assert result_metadata["about"]["license"] == "MIT"
    
    # Check requirements
    expected_imports = ["r-base", "r-dplyr >=1.0.0", "r-ggplot2"]
    assert sorted(result_metadata["requirements"]["host"]) == expected_imports
    assert sorted(result_metadata["requirements"]["run"]) == expected_imports
    
    # Check test commands
    test_commands = result_metadata["test"]["commands"]
    assert '$R -e "library(\'rpkg\')"  # [not win]' in test_commands
    assert '"%R%" -e "library(\'rpkg\')"  # [win]' in test_commands
    
    # Check recipe comment
    assert "# Package: rpkg" in r_recipe_comment
    assert "# Version: 1.0.0" in r_recipe_comment
    assert "# License: MIT" in r_recipe_comment


@patch("grayskull.strategy.cran.handle_gh_version")
@patch("grayskull.strategy.cran.generate_git_archive_tarball_url")
@patch("grayskull.strategy.cran.download_github_r_pkg")
@patch("grayskull.strategy.cran.get_archive_metadata")
@patch("grayskull.strategy.cran.sha256_checksum")
def test_get_github_r_metadata_with_compilation(
    mock_sha256,
    mock_get_archive_metadata,
    mock_download_github_r_pkg,
    mock_generate_archive_url,
    mock_handle_gh_version,
    tmp_path,
):
    """Test getting metadata for R package that needs compilation"""
    
    # Setup mocks
    mock_handle_gh_version.return_value = ("1.0.0", "v1.0.0")
    mock_generate_archive_url.return_value = "https://github.com/user/rpkg/archive/v1.0.0.tar.gz"
    mock_download_github_r_pkg.return_value = str(tmp_path / "rpkg-v1.0.0.tar.gz")
    mock_sha256.return_value = "abc123"
    mock_get_archive_metadata.return_value = {
        "orig_lines": ["Package: rpkg", "Version: 1.0.0"],
        "Package": "rpkg",
        "Version": "1.0.0",
        "License": "GPL-3",
        "Description": "A test R package with compilation",
        "Imports": "",
        "NeedsCompilation": "yes",
    }
    
    # Test configuration
    config = Configuration(name="https://github.com/user/rpkg", version="1.0.0")
    
    # Call the function
    result_metadata, r_recipe_comment = get_github_r_metadata(config)
    
    # Check that compilation requirements are added
    assert result_metadata["need_compiler"] is True
    build_requirements = result_metadata["requirements"]["build"]
    assert "cross-r-base {{ r_base }}  # [build_platform != target_platform]" in build_requirements
    assert "{{ compiler('c') }}  # [unix]" in build_requirements
    assert "{{ compiler('cxx') }}  # [unix]" in build_requirements


@patch("grayskull.strategy.cran.requests.get")
@patch("grayskull.strategy.cran.mkdtemp")
def test_download_github_r_pkg(mock_mkdtemp, mock_requests_get, tmp_path):
    """Test downloading R package from GitHub"""
    
    # Setup mocks
    mock_mkdtemp.return_value = str(tmp_path)
    mock_response = MagicMock()
    mock_response.content = b"fake_tarball_content"
    mock_response.raise_for_status.return_value = None
    mock_requests_get.return_value = mock_response
    
    config = Configuration(name="test_pkg")
    archive_url = "https://github.com/user/test_pkg/archive/v1.0.0.tar.gz"
    pkg_name = "test_pkg"
    version_tag = "v1.0.0"
    
    # Call the function
    download_file = download_github_r_pkg(config, archive_url, pkg_name, version_tag)
    
    # Verify the download
    assert download_file == str(tmp_path / f"{pkg_name}-{version_tag}.tar.gz")
    assert os.path.exists(download_file)
    
    # Verify file content
    with open(download_file, "rb") as f:
        content = f.read()
    assert content == b"fake_tarball_content"
    
    # Verify requests was called correctly
    mock_requests_get.assert_called_once_with(archive_url)
    mock_response.raise_for_status.assert_called_once()


def test_github_url_package_name_extraction():
    """Test extracting package name from GitHub URLs"""
    from grayskull.strategy.cran import get_github_r_metadata
    
    # Test one specific case that should work
    github_url = "https://github.com/user/repo"
    expected_name = "repo"
    
    with patch("grayskull.strategy.cran.handle_gh_version") as mock_handle, \
         patch("grayskull.strategy.cran.generate_git_archive_tarball_url") as mock_archive, \
         patch("grayskull.strategy.cran.download_github_r_pkg") as mock_download, \
         patch("grayskull.strategy.cran.get_archive_metadata") as mock_metadata, \
         patch("grayskull.strategy.cran.sha256_checksum") as mock_sha256, \
         patch("grayskull.strategy.cran.print_msg"):
        
        # Setup basic mocks
        mock_handle.return_value = ("1.0.0", "v1.0.0")
        mock_archive.return_value = "https://example.com/archive.tar.gz"
        mock_download.return_value = "/tmp/file.tar.gz"
        mock_sha256.return_value = "abc123"
        mock_metadata.return_value = {
            "orig_lines": [],
            "Package": expected_name,
            "Version": "1.0.0",
            "License": "MIT",
            "Description": "Test package",
            "Imports": "",
            "NeedsCompilation": "no",
        }
        
        config = Configuration(name=github_url)
        result_metadata, _ = get_github_r_metadata(config)
        
        # Verify that the test command uses the correct package name
        test_commands = result_metadata["test"]["commands"]
        assert f'$R -e "library(\'{expected_name}\')"  # [not win]' in test_commands