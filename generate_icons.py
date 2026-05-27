import os
from PIL import Image, ImageDraw, ImageFilter

def create_heartbeat_points(width, height):
    # Proportions for a nice ECG pulse wave
    mid_y = height // 2
    # Define vertices scaled to width/height
    w_scale = width / 32.0
    h_scale = height / 32.0
    
    return [
        (0 * w_scale, mid_y),
        (8 * w_scale, mid_y),
        (10 * w_scale, mid_y + 2 * h_scale),
        (13 * w_scale, mid_y - 12 * h_scale),
        (16 * w_scale, mid_y + 12 * h_scale),
        (20 * w_scale, mid_y - 4 * h_scale),
        (23 * w_scale, mid_y),
        (32 * w_scale, mid_y)
    ]

def draw_gradient_background(draw, width, height):
    # Linear gradient from top-left (deep purple) to bottom-right (dark slate blue)
    for y in range(height):
        for x in range(width):
            # Calculate gradient factor
            factor = (x + y) / (width + height)
            
            # Purple: (46, 8, 84) -> Blue-Slate: (11, 26, 48)
            r = int(46 + (11 - 46) * factor)
            g = int(8 + (26 - 8) * factor)
            b = int(84 + (48 - 84) * factor)
            
            draw.point((x, y), fill=(r, g, b, 255))

def generate_app_icon(path):
    width, height = 512, 512
    # Create canvas
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 1. Draw rounded rectangle background (simulating app border)
    # Draw background with gradient
    bg_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg_img)
    draw_gradient_background(bg_draw, width, height)
    
    # Create a mask for rounded rectangle
    mask = Image.new("L", (width, height), 0)
    mask_draw = ImageDraw.Draw(mask)
    # 64px corner radius
    mask_draw.rounded_rectangle([20, 20, width-20, height-20], radius=64, fill=255)
    
    # Apply mask
    app_bg = Image.composite(bg_img, Image.new("RGBA", (width, height), (0, 0, 0, 0)), mask)
    
    # 2. Draw border
    border_draw = ImageDraw.Draw(app_bg)
    border_draw.rounded_rectangle([20, 20, width-20, height-20], radius=64, outline=(255, 255, 255, 30), width=6)
    
    # 3. Draw heartbeat with glow
    # Heartbeat path coordinates (scaled)
    points = create_heartbeat_points(width - 80, height - 80)
    # Offset points to center them in the inner box (offset by 40px)
    offset_points = [(x + 40, y + 40) for (x, y) in points]
    
    # Draw glowing line layers
    # Layer 1: Wide blur glow (cyan/purple mix glow)
    glow_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_img)
    glow_draw.line(offset_points, fill=(124, 77, 255, 180), width=24, joint="round")
    glow_img = glow_img.filter(ImageFilter.GaussianBlur(15))
    
    # Layer 2: Medium glow (neon cyan/indigo)
    mid_glow_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    mid_glow_draw = ImageDraw.Draw(mid_glow_img)
    mid_glow_draw.line(offset_points, fill=(0, 229, 255, 225), width=12, joint="round")
    mid_glow_img = mid_glow_img.filter(ImageFilter.GaussianBlur(5))
    
    # Layer 3: Central sharp white core
    core_img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    core_draw = ImageDraw.Draw(core_img)
    core_draw.line(offset_points, fill=(255, 255, 255, 255), width=6, joint="round")
    
    # Combine layers
    final_img = Image.alpha_composite(app_bg, glow_img)
    final_img = Image.alpha_composite(final_img, mid_glow_img)
    final_img = Image.alpha_composite(final_img, core_img)
    
    final_img.save(path, "PNG")
    print(f"App icon saved to {path}")

def generate_tray_icon(path, color):
    # Tray icon size for Linux is standard 32x32 or 22x22. We use 32x32.
    width, height = 32, 32
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Heartbeat path coordinates
    points = create_heartbeat_points(width, height)
    
    # Draw simple clean heartbeat line with given color
    # We add a subtle glow even for tray icon if desired, but clean sharp lines are better for small tray icons.
    # To make it stand out, we draw a shadow first, then the colored line.
    shadow_color = (0, 0, 0, 100)
    shadow_points = [(x, y + 1) for (x, y) in points]
    draw.line(shadow_points, fill=shadow_color, width=3, joint="round")
    
    draw.line(points, fill=color, width=3, joint="round")
    
    img.save(path, "PNG")
    print(f"Tray icon saved to {path}")

if __name__ == "__main__":
    # Utilizar ruta relativa a la ubicación del script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(script_dir, "assets")
    if not os.path.exists(assets_dir):
        os.makedirs(assets_dir)
        
    # Generate main application icon
    generate_app_icon(os.path.join(assets_dir, "app-icon.png"))
    
    # Generate tray status icons
    # Idle: Silver/Gray-blue (156, 163, 175)
    generate_tray_icon(os.path.join(assets_dir, "icon-idle.png"), (156, 163, 175, 255))
    
    # Online: Bright Emerald Green (16, 185, 129)
    generate_tray_icon(os.path.join(assets_dir, "icon-online.png"), (16, 185, 129, 255))
    
    # Offline: Pulsing Red (239, 68, 68)
    generate_tray_icon(os.path.join(assets_dir, "icon-offline.png"), (239, 68, 68, 255))
    
    print("All icons successfully generated!")
