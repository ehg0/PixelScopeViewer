# Manual Test Guide: Channel Settings Preservation

This guide explains how to manually test that graph properties are preserved when switching between images in the Analysis dialog.

## Prerequisites
- Multiple test images with different channel counts (RGB, RGBA, grayscale)
- PySide6 image viewer application running

## Test Scenario 1: Switching Between Same Channel Count Images

### Steps:
1. Load two 3-channel RGB images (e.g., `test_rgb_1.png`, `test_rgb_2.png`)
2. Open Analysis dialog (Menu > 解析 > Show Analysis)
3. Switch to Histogram or Profile tab
4. Click "Configure..." button under Channels
5. Uncheck channel 1 (green channel)
6. Close the channel configuration dialog
7. **Verify**: Only red (channel 0) and blue (channel 2) are displayed
8. Switch to the next image (press 'n' key)
9. **Expected Result**: The channel settings should be preserved - only channels 0 and 2 are visible
10. **Bug (before fix)**: All channels would be visible again

### Expected Behavior:
✅ Channel visibility settings (0: visible, 1: hidden, 2: visible) are preserved

## Test Scenario 2: Switching to Image with More Channels

### Steps:
1. Load a 3-channel RGB image and a 4-channel RGBA image
2. Open Analysis dialog on the RGB image
3. Switch to Histogram or Profile tab
4. Configure channels: uncheck channel 1
5. **Verify**: Channels 0 and 2 are visible, channel 1 is hidden
6. Switch to the RGBA image (press 'n')
7. **Expected Result**: 
   - Channels 0 and 2 maintain their visibility settings (0: visible, 2: visible)
   - Channel 1 remains hidden
   - New channel 3 (alpha) is visible by default
8. **Bug (before fix)**: Would crash with IndexError when trying to access channel 3

### Expected Behavior:
✅ Existing channel settings preserved
✅ New channels default to visible
✅ No crashes or errors

## Test Scenario 3: Switching to Image with Fewer Channels

### Steps:
1. Load a 4-channel RGBA image and a 1-channel grayscale image
2. Open Analysis dialog on the RGBA image
3. Switch to Histogram or Profile tab
4. Configure channels: uncheck channels 1 and 3
5. **Verify**: Channels 0 and 2 are visible
6. Switch to the grayscale image (press 'n')
7. **Expected Result**: The single channel is displayed
8. Switch back to the RGBA image (press 'b')
9. **Expected Result**: The channel settings are restored (channels 0 and 2 visible, 1 and 3 hidden)

### Expected Behavior:
✅ Channel settings gracefully handle fewer channels
✅ Settings are restored when switching back to multi-channel image

## Test Scenario 4: Other Property Preservation

These properties should also be preserved when switching images:

### Profile Orientation:
1. Open Analysis dialog, switch to Profile tab
2. Click "Horizontal" button to change to "Vertical"
3. Switch to next image
4. **Expected**: Profile remains in Vertical mode

### Profile X-Axis Mode:
1. In Profile tab, click "Relative" button to change to "Absolute"
2. Switch to next image
3. **Expected**: Profile remains in Absolute mode

### Histogram Y-Axis Scale:
1. In Histogram tab, right-click on the plot
2. Select "Log Y axis" (or similar option)
3. Switch to next image
4. **Expected**: Histogram remains in log scale mode

## Verification Checklist

- [ ] Channel visibility settings preserved for same channel count
- [ ] Channel settings extended correctly for images with more channels
- [ ] No crashes when switching to images with different channel counts
- [ ] Profile orientation preserved (Horizontal/Vertical/Diagonal)
- [ ] Profile X-axis mode preserved (Relative/Absolute)
- [ ] Histogram Y-axis scale preserved (Linear/Log)
- [ ] Settings persist across multiple image switches
- [ ] Settings restored when switching back to previous images

## Notes

The fix ensures that the `channel_checks` list is dynamically adjusted when the number of channels changes:
- If new image has more channels: extend the list with `True` (visible) for new channels
- If new image has fewer channels: only use the first N elements (no change needed to the list)
- If new image has same channels: list is unchanged (existing behavior)

This allows users to configure their preferred channel visibility once and have those settings persist across all images with similar channel counts.
