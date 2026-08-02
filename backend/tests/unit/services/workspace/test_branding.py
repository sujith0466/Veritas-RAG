"""Unit tests for F3.7 Workspace Branding (CSS Variables & Validation)."""

from datetime import datetime, timezone
import uuid
import pytest
from pydantic import ValidationError

from backend.api.v1.schemas.workspace_settings import (
    BrandingSettings,
    calculate_relative_luminance,
    calculate_contrast_ratio,
)
from backend.services.workspace.settings_service import (
    compile_branding_css_variables,
    compile_css_string,
    compile_tailwind_tokens,
)


def test_wcag_luminance_and_contrast():
    # White on Black should be ~21.0
    white_lum = calculate_relative_luminance("#ffffff")
    black_lum = calculate_relative_luminance("#000000")
    assert white_lum > black_lum
    ratio = calculate_contrast_ratio("#ffffff", "#000000")
    assert ratio >= 21.0

    # Same color ratio should be 1.0
    assert calculate_contrast_ratio("#ffffff", "#ffffff") == 1.0


def test_wcag_aa_validation_pass_and_fail():
    # Valid contrast: Black text on primary background
    assert calculate_contrast_ratio("#000000", "#ffffff") >= 4.5

    # Invalid contrast: Light gray on white -> Ratio < 3.0
    assert calculate_contrast_ratio("#f0f0f0", "#ffffff") < 3.0



def test_branding_settings_defaults():
    settings = BrandingSettings()
    assert settings.primary_color == "#0ea5e9"
    assert settings.theme_mode.value == "SYSTEM"
    assert settings.font_family == "Inter, sans-serif"


def test_branding_settings_invalid_hex():
    with pytest.raises(ValidationError):
        BrandingSettings(primary_color="not-a-color")


def test_compile_branding_css_variables():
    branding = {
        "primary_color": "#2563eb",
        "secondary_color": "#475569",
        "accent_color": "#7c3aed",
        "success_color": "#059669",
        "warning_color": "#d97706",
        "danger_color": "#dc2626",
        "info_color": "#2563eb",
        "font_family": "Roboto, sans-serif",
        "border_radius": "0.5rem",
        "logo_url": "https://cdn.example.com/logo.png",
        "logo_version": 3,
        "logo_etag": "abc123etag",
        "custom_css_variables": {
            "--header-height": "64px",
            "sidebar-width": "250px",
        },
    }

    css_vars = compile_branding_css_variables(branding)

    assert css_vars["--brand-primary"] == "#2563eb"
    assert css_vars["--brand-font-family"] == "Roboto, sans-serif"
    assert css_vars["--brand-border-radius"] == "0.5rem"
    assert "https://cdn.example.com/logo.png?v=3&etag=abc123etag" in css_vars["--brand-logo-url"]
    assert css_vars["--header-height"] == "64px"
    assert css_vars["--sidebar-width"] == "250px"


def test_compile_css_string():
    css_vars = {
        "--brand-primary": "#2563eb",
        "--brand-font-family": "Inter, sans-serif",
    }
    css_str = compile_css_string(css_vars)
    assert ":root {" in css_str
    assert "  --brand-primary: #2563eb;" in css_str
    assert "  --brand-font-family: Inter, sans-serif;" in css_str


def test_compile_tailwind_tokens():
    branding = {"primary_color": "#2563eb"}
    tokens = compile_tailwind_tokens(branding)
    assert tokens["colors"]["brand"]["primary"] == "var(--brand-primary)"
    assert tokens["borderRadius"]["brand"] == "var(--brand-border-radius)"
    assert tokens["fontFamily"]["brand"] == "var(--brand-font-family)"
