import numpy as np
from PIL import Image
from io import BytesIO


def mirror(file: str | BytesIO) -> BytesIO:
    img = Image.open(file)
    width, height = img.size

    lane_start_x = 80  # Start of lanes
    lane_width = 192  # Width of each lane
    lane_spacing = 272  # Distance between lanes
    lane_height = height - 287  # 287px of info, the chart info

    img_array = np.array(img)

    # for each lane, mirror
    for i in range(round((width - lane_start_x) / lane_spacing)):
        lane_x = lane_start_x + (i * lane_spacing)
        if lane_x + lane_width > width:
            break  # Prevent out-of-bounds errors

        # flip lane horizontally
        img_array[:lane_height, lane_x : lane_x + lane_width] = np.fliplr(
            img_array[:lane_height, lane_x : lane_x + lane_width]
        )

    output = Image.fromarray(img_array)

    result = BytesIO()
    output.save(result, format="png")
    result.seek(0)
    return result
