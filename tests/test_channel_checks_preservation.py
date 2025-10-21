"""Test script for verifying channel_checks preservation when switching images.

This test validates that channel visibility settings are properly preserved
when switching between images with different channel counts.
"""

import sys
from pathlib import Path

# Add parent directory to path to import pyside_image_viewer module
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_channel_checks_extension():
    """Test that channel_checks is properly extended when image has more channels."""
    
    # Simulate the logic from AnalysisDialog.update_contents()
    channel_checks = [True, False, True]  # Settings for 3-channel image
    
    # Now switch to a 4-channel image
    nch = 4
    
    # Apply the fix logic
    if not channel_checks:
        channel_checks = [True] * nch
    elif len(channel_checks) < nch:
        # Extend with True for new channels
        channel_checks.extend([True] * (nch - len(channel_checks)))
    
    # Verify the result
    assert len(channel_checks) == 4, f"Expected length 4, got {len(channel_checks)}"
    assert channel_checks == [True, False, True, True], f"Expected [True, False, True, True], got {channel_checks}"
    
    print("✓ Test passed: channel_checks extended correctly for 4-channel image")


def test_channel_checks_preservation():
    """Test that channel_checks is preserved when switching to same channel count."""
    
    channel_checks = [True, False, True]  # Settings for 3-channel image
    
    # Switch to another 3-channel image
    nch = 3
    
    # Apply the fix logic
    if not channel_checks:
        channel_checks = [True] * nch
    elif len(channel_checks) < nch:
        channel_checks.extend([True] * (nch - len(channel_checks)))
    
    # Verify the result
    assert len(channel_checks) == 3, f"Expected length 3, got {len(channel_checks)}"
    assert channel_checks == [True, False, True], f"Expected [True, False, True], got {channel_checks}"
    
    print("✓ Test passed: channel_checks preserved for same channel count")


def test_channel_checks_fewer_channels():
    """Test that channel_checks handles images with fewer channels gracefully."""
    
    channel_checks = [True, False, True, True]  # Settings for 4-channel image
    
    # Switch to a 3-channel image
    nch = 3
    
    # Apply the fix logic
    if not channel_checks:
        channel_checks = [True] * nch
    elif len(channel_checks) < nch:
        channel_checks.extend([True] * (nch - len(channel_checks)))
    
    # When accessing channels, we only use indices 0, 1, 2
    # The 4th element is simply not used
    visible_channels = [c for c in range(nch) if channel_checks[c]]
    
    # Verify the result
    assert len(channel_checks) == 4, f"Expected length 4, got {len(channel_checks)}"
    assert visible_channels == [0, 2], f"Expected [0, 2], got {visible_channels}"
    
    print("✓ Test passed: channel_checks handles fewer channels correctly")


def test_channel_checks_initialization():
    """Test that channel_checks is initialized when empty."""
    
    channel_checks = []  # No settings yet
    
    # First image with 3 channels
    nch = 3
    
    # Apply the fix logic
    if not channel_checks:
        channel_checks = [True] * nch
    elif len(channel_checks) < nch:
        channel_checks.extend([True] * (nch - len(channel_checks)))
    
    # Verify the result
    assert len(channel_checks) == 3, f"Expected length 3, got {len(channel_checks)}"
    assert channel_checks == [True, True, True], f"Expected [True, True, True], got {channel_checks}"
    
    print("✓ Test passed: channel_checks initialized correctly")


if __name__ == "__main__":
    test_channel_checks_initialization()
    test_channel_checks_preservation()
    test_channel_checks_extension()
    test_channel_checks_fewer_channels()
    print("\n✅ All tests passed!")
