"""Drawing utilities for modern UI elements."""

import math
from typing import List, Tuple, Optional
import pygame


def draw_rounded_rect(
    surface: pygame.Surface,
    color: Tuple[int, int, int],
    rect: pygame.Rect,
    radius: int = 15,
    border_width: int = 0,
    border_color: Optional[Tuple[int, int, int]] = None
) -> None:
    """
    Draw a rectangle with rounded corners.

    Args:
        surface: Surface to draw on
        color: Fill color (RGB tuple)
        rect: Rectangle dimensions
        radius: Corner radius
        border_width: Border width (0 for no border)
        border_color: Border color (defaults to fill color)
    """
    if radius > min(rect.width, rect.height) // 2:
        radius = min(rect.width, rect.height) // 2

    # Draw filled rounded rectangle
    pygame.draw.rect(surface, color, rect, border_radius=radius)

    # Draw border if specified
    if border_width > 0:
        border_col = border_color if border_color else color
        pygame.draw.rect(surface, border_col, rect, border_width, border_radius=radius)


def draw_smooth_line(
    surface: pygame.Surface,
    color: Tuple[int, int, int],
    points: List[Tuple[float, float]],
    width: int = 3,
    smoothness: int = 10
) -> None:
    """
    Draw a smooth curved line through the given points using Catmull-Rom spline.

    Args:
        surface: Surface to draw on
        color: Line color
        points: List of (x, y) points
        width: Line width
        smoothness: Number of interpolated points between each pair
    """
    if len(points) < 2:
        return

    if len(points) == 2:
        pygame.draw.line(surface, color, points[0], points[1], width)
        return

    # Generate smooth curve using Catmull-Rom spline
    smooth_points = []

    for i in range(len(points) - 1):
        # Get 4 control points for Catmull-Rom
        p0 = points[max(0, i - 1)]
        p1 = points[i]
        p2 = points[min(len(points) - 1, i + 1)]
        p3 = points[min(len(points) - 1, i + 2)]

        # Interpolate between p1 and p2
        for t_step in range(smoothness + 1):
            t = t_step / smoothness

            # Catmull-Rom spline formula
            t2 = t * t
            t3 = t2 * t

            x = 0.5 * (
                2 * p1[0] +
                (-p0[0] + p2[0]) * t +
                (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 +
                (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                2 * p1[1] +
                (-p0[1] + p2[1]) * t +
                (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 +
                (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )

            smooth_points.append((x, y))

    # Draw the smooth curve
    if len(smooth_points) > 1:
        pygame.draw.lines(surface, color, False, smooth_points, width)


def draw_gradient_rect(
    surface: pygame.Surface,
    rect: pygame.Rect,
    color_top: Tuple[int, int, int],
    color_bottom: Tuple[int, int, int],
    radius: int = 0
) -> None:
    """
    Draw a rectangle with a vertical gradient.

    Args:
        surface: Surface to draw on
        rect: Rectangle dimensions
        color_top: Top color
        color_bottom: Bottom color
        radius: Corner radius (0 for sharp corners)
    """
    # Create a temporary surface for the gradient
    gradient_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)

    for y in range(rect.height):
        ratio = y / rect.height
        r = int(color_top[0] + (color_bottom[0] - color_top[0]) * ratio)
        g = int(color_top[1] + (color_bottom[1] - color_top[1]) * ratio)
        b = int(color_top[2] + (color_bottom[2] - color_top[2]) * ratio)
        pygame.draw.line(gradient_surface, (r, g, b), (0, y), (rect.width, y))

    # Apply rounded corners if needed
    if radius > 0:
        # Create a mask for rounded corners
        mask_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        pygame.draw.rect(mask_surface, (255, 255, 255, 255),
                        pygame.Rect(0, 0, rect.width, rect.height),
                        border_radius=radius)
        gradient_surface.blit(mask_surface, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)

    surface.blit(gradient_surface, rect.topleft)


def draw_shadow(
    surface: pygame.Surface,
    rect: pygame.Rect,
    radius: int = 15,
    shadow_offset: int = 4,
    shadow_color: Tuple[int, int, int, int] = (0, 0, 0, 60)
) -> None:
    """
    Draw a drop shadow for a rounded rectangle.

    Args:
        surface: Surface to draw on
        rect: Rectangle to shadow
        radius: Corner radius
        shadow_offset: Offset of shadow
        shadow_color: Shadow color with alpha
    """
    shadow_surface = pygame.Surface(
        (rect.width + shadow_offset * 2, rect.height + shadow_offset * 2),
        pygame.SRCALPHA
    )

    shadow_rect = pygame.Rect(shadow_offset, shadow_offset, rect.width, rect.height)
    pygame.draw.rect(shadow_surface, shadow_color, shadow_rect, border_radius=radius)

    surface.blit(shadow_surface, (rect.x - shadow_offset // 2, rect.y))


def draw_circle_icon(
    surface: pygame.Surface,
    center: Tuple[int, int],
    radius: int,
    bg_color: Tuple[int, int, int],
    icon_color: Tuple[int, int, int],
    icon_text: str,
    font: pygame.font.Font
) -> None:
    """
    Draw a circular icon with text/emoji.

    Args:
        surface: Surface to draw on
        center: Center position
        radius: Circle radius
        bg_color: Background color
        icon_color: Icon/text color
        icon_text: Text or emoji to display
        font: Font to use
    """
    pygame.draw.circle(surface, bg_color, center, radius)

    text_surface = font.render(icon_text, True, icon_color)
    text_rect = text_surface.get_rect(center=center)
    surface.blit(text_surface, text_rect)


def lerp_color(
    color1: Tuple[int, int, int],
    color2: Tuple[int, int, int],
    t: float
) -> Tuple[int, int, int]:
    """
    Linear interpolation between two colors.

    Args:
        color1: Start color
        color2: End color
        t: Interpolation factor (0-1)

    Returns:
        Interpolated color
    """
    t = max(0, min(1, t))
    return (
        int(color1[0] + (color2[0] - color1[0]) * t),
        int(color1[1] + (color2[1] - color1[1]) * t),
        int(color1[2] + (color2[2] - color1[2]) * t)
    )
