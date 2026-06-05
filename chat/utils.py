import urllib.parse

"""
This module provides shared helper utilities for the chat application.
"""

def get_avatar_svg(name, bg_color="#6366f1"):
    """
    Generates a dynamic avatar SVG based on user initials and encodes it as a data URI string.
    This provides an efficient, database-free way to render placeholders for users without profile pictures.

    Parameters:
    - name: Username or full name.
    - bg_color: Optional starting hex color, defaults to HSL hash generator color selection.
    """
    # If bg_color is default or missing, derive a color hash based on the name characters
    if bg_color == "#6366f1" or not bg_color:
        hash_val = 0
        for char in name:
            hash_val = ord(char) + ((hash_val << 5) - hash_val)
        colors = [
            '#6366f1', '#3b82f6', '#10b981', '#f59e0b', '#ef4444', 
            '#ec4899', '#8b5cf6', '#06b6d4', '#14b8a6', '#f43f5e'
        ]
        # Choose a color consistently from the list
        bg_color = colors[abs(hash_val) % len(colors)]
    
    # Parse first-letter initials
    parts = name.strip().split()
    initials = "".join(p[0].upper() for p in parts[:2]) if parts else "U"
    if not initials:
        initials = "U"
        
    # Construct raw SVG element XML text
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100%" height="100%">
        <rect width="100" height="100" fill="{bg_color}"/>
        <text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-size="40" font-family="sans-serif" font-weight="bold" fill="#ffffff">{initials}</text>
    </svg>"""
    
    # URL-encode the SVG XML string to construct a data URI representation
    encoded_svg = urllib.parse.quote(svg)
    return f"data:image/svg+xml,{encoded_svg}"
