"""가벼운 자체 셰이더 (GLSL 1.30).

ursina 기본 lit_with_shadows_shader 는 일부 OpenGL 드라이버(예: Mesa llvmpipe 소프트웨어 렌더러)에서
그리는 순간 프로세스를 죽이는 문제가 있어, 그림자 맵 없이 방향광 + 환경광 + 거리 안개만 계산하는
셰이더를 직접 쓴다. 나무 그림자는 지형 텍스처에 미리 구워 넣는다 (tools/art/gen_textures3d.py).
"""
from ursina import Vec2, Vec3
from ursina.shader import Shader

LIGHT = {
    "sun_dir": Vec3(0.45, -0.8, 0.4).normalized(),     # 빛이 향하는 방향
    "sun_color": Vec3(1.0, 0.95, 0.84),
    "ambient": Vec3(0.55, 0.58, 0.66),
    "fog_color": Vec3(0.67, 0.77, 0.84),
    "fog_start": 34.0,
    "fog_end": 90.0,
}

_VERT = """#version 130
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
uniform mat3 p3d_NormalMatrix;
uniform mat4 p3d_ViewMatrixInverse;
in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec2 p3d_MultiTexCoord0;
in vec4 p3d_Color;
uniform vec2 texture_scale;
uniform vec2 texture_offset;
out vec2 uv;
out vec4 vcolor;
out vec3 wpos;
out vec3 wnormal;
void main() {
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    uv = p3d_MultiTexCoord0 * texture_scale + texture_offset;
    vcolor = p3d_Color;
    wpos = (p3d_ModelMatrix * p3d_Vertex).xyz;
    wnormal = normalize(mat3(p3d_ModelMatrix) * p3d_Normal);
}
"""

_FRAG_LIT = """#version 130
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform vec3 sun_dir;
uniform vec3 sun_color;
uniform vec3 ambient;
uniform vec3 fog_color;
uniform float fog_start;
uniform float fog_end;
uniform vec3 camera_world_position;
in vec2 uv;
in vec4 vcolor;
in vec3 wpos;
in vec3 wnormal;
out vec4 frag;
void main() {
    vec4 c = texture(p3d_Texture0, uv) * p3d_ColorScale * vcolor;
    if (c.a < 0.35) discard;
    vec3 n = normalize(wnormal);
    float lambert = max(dot(n, -sun_dir), 0.0);
    float wrap = clamp(dot(n, -sun_dir) * 0.5 + 0.5, 0.0, 1.0);   // 부드러운 반사광
    vec3 light = ambient * (0.75 + 0.25 * wrap) + sun_color * lambert;
    c.rgb *= light;
    float t = clamp((length(wpos - camera_world_position) - fog_start) / (fog_end - fog_start), 0.0, 1.0);
    c.rgb = mix(c.rgb, fog_color, t);
    frag = c;
}
"""

_FRAG_UNLIT = """#version 130
uniform sampler2D p3d_Texture0;
uniform vec4 p3d_ColorScale;
uniform vec3 fog_color;
uniform float fog_start;
uniform float fog_end;
uniform vec3 camera_world_position;
in vec2 uv;
in vec4 vcolor;
in vec3 wpos;
in vec3 wnormal;
out vec4 frag;
void main() {
    vec4 c = texture(p3d_Texture0, uv) * p3d_ColorScale * vcolor;
    if (c.a < 0.02) discard;
    float t = clamp((length(wpos - camera_world_position) - fog_start) / (fog_end - fog_start), 0.0, 1.0);
    c.rgb = mix(c.rgb, fog_color, t);
    frag = c;
}
"""


def _cam_pos():
    from ursina import camera
    return camera.world_position


def _make(name, frag):
    sh = Shader(name=name, language=Shader.GLSL, vertex=_VERT, fragment=frag,
                default_input={"texture_scale": Vec2(1, 1), "texture_offset": Vec2(0, 0),
                               "camera_world_position": Vec3(0, 0, 0), **LIGHT})
    sh.continuous_input["camera_world_position"] = _cam_pos
    return sh


lit_shader = _make("field_lit", _FRAG_LIT)
unlit_shader = _make("field_unlit", _FRAG_UNLIT)


# ---------------------------------------------------------------- 타일 텍스처 지형 (splat)
# p3d_Texture0 = 분포 맵 (R: 흙길, G: 돌바닥, B: 구워 둔 그림자), 잔디/흙/돌 타일은 월드 좌표로 반복
_FRAG_TERRAIN = """#version 130
uniform sampler2D p3d_Texture0;
uniform sampler2D grass_tex;
uniform sampler2D dirt_tex;
uniform sampler2D stone_tex;
uniform float tile;
uniform vec3 sun_dir;
uniform vec3 sun_color;
uniform vec3 ambient;
uniform vec3 fog_color;
uniform float fog_start;
uniform float fog_end;
uniform vec3 camera_world_position;
in vec2 uv;
in vec4 vcolor;
in vec3 wpos;
in vec3 wnormal;
out vec4 frag;
void main() {
    vec4 sp = texture(p3d_Texture0, uv);
    vec2 t = wpos.xz / tile;
    // 같은 타일을 두 배율로 섞어 반복 무늬가 덜 보이게
    vec3 g = mix(texture(grass_tex, t).rgb, texture(grass_tex, t * 0.37 + 0.21).rgb, 0.35);
    vec3 d = mix(texture(dirt_tex, t).rgb, texture(dirt_tex, t * 0.41 + 0.6).rgb, 0.3);
    vec3 s = texture(stone_tex, t * 0.8).rgb;
    g *= vec3(0.86, 0.84, 0.8);                      // 생성 잔디의 높은 채도를 숲 색감에 맞춰 낮춤
    d *= vec3(0.86, 0.84, 0.8);                      // 흙길이 하얗게 뜨지 않게
    vec3 c = mix(g, d, sp.r);
    c = mix(c, s, sp.g);
    c *= 1.0 - sp.b * 0.55;
    vec3 n = normalize(wnormal);
    float lambert = max(dot(n, -sun_dir), 0.0);
    c *= ambient * 0.95 + sun_color * lambert * 0.85;
    float f = clamp((length(wpos - camera_world_position) - fog_start) / (fog_end - fog_start), 0.0, 1.0);
    frag = vec4(mix(c, fog_color, f), 1.0);
}
"""

terrain_shader = Shader(name="field_terrain", language=Shader.GLSL, vertex=_VERT, fragment=_FRAG_TERRAIN,
                        default_input={"texture_scale": Vec2(1, 1), "texture_offset": Vec2(0, 0), "tile": 4.0,
                                       "camera_world_position": Vec3(0, 0, 0), **LIGHT})
terrain_shader.continuous_input["camera_world_position"] = _cam_pos
