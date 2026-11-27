# 황동의 심장 : 아스카론 연대기

2000년대 초반 국산 PC RPG 감성의 2.5D 쿼터뷰 스팀펑크 판타지 RPG. 본편은 **3D 쿼터뷰 버전**(ursina / Panda3D)이다.
현재 3장 '녹슨 숲' 구간(베르단 숲 어귀 → 고목의 요람 → 공명의 제단 → 보스 '숲 채굴기 그라인더')을 플레이할 수 있다.
이전 2D(pygame) 데모(프롤로그~1장)는 `main2d.py` 로 남겨 두었다.

## 실행

```bash
pip install -r requirements.txt
python main.py      # 3D 본편: 타이틀 → 새 게임 / 이어하기
python main2d.py    # 이전 2D 데모
```

Windows 실행 파일: GitHub Actions 의 **Build Windows EXE** 워크플로가 `Arcturus_RPG.exe` 하나로 만들어 Artifacts 에 올린다.
직접 빌드: `pip install pyinstaller && python tools/build_exe.py` → `dist/Arcturus_RPG.exe`

### 조작 (3D, `main.py`, `src3d/`)
| 키 | 동작 |
|---|---|
| WASD / 방향키 | 이동 (카메라 기준) · 메뉴 커서 |
| Z / Space / Enter | 대화 · 다음 대사 · 결정 |
| X / Esc / Tab | 필드 메뉴 · 취소 |
| Q / E | 카메라 45° 회전 |
| 마우스 휠 | 확대 / 축소 |

- **타이틀**: 숲 위를 천천히 도는 카메라 + 새 게임 / 이어하기(3D 세이브가 있을 때) / 종료
- **필드 메뉴**: 상태(능력치·스킬·반신 일러스트, ◀▶ 동료 전환) / 아이템(대상 선택 사용) / 저장 / 불러오기 / 타이틀로 / 게임 종료.
  세이브는 2D 와 같은 슬롯 3개·같은 폴더를 쓰며, 2D 세이브는 3D 에서 '불러올 수 없음'으로 표시된다
- **맵 이동**: 맵 JSON 의 `exits` (위치·반경·도착 맵·도착 지점) → 페이드 아웃/인
- **스토리 이벤트**: 맵 JSON 의 `intro_scene`(첫 방문), `events` — `talk`(NPC 첫 대화), `zone`(구역 진입) 이벤트가
  `steps` 를 차례로 실행: `scene`(story.json 장면) → `battle`(보스전) → `flag` → `banner`. 본 장면·끝난 이벤트는 플래그로 기억(세이브됨)
- 높이맵 지형(언덕·흙길·잔디 텍스처, 나무 그림자는 텍스처에 구움), 입체 나무·덤불·바위, 풀포기·꽃
- 항상 카메라를 바라보는 빌보드 캐릭터 + 발밑 그림자, 동료 2명이 발자취를 따라 걸음, 카메라 회전 시 앞/뒷모습 자동 전환
- **ATB 전투** (`src3d/battle3d.py`, 규칙은 2D 와 공용인 `src/systems/battle_core.py`): 걷다 보면 랜덤 인카운트 →
  그 자리 지형 위에서 파티·적 빌보드가 마주 서고 카메라가 전투 구도로 이동. 명령(공격/스킬/방어/아이템/도주),
  대상 지정, 돌진·가산 합성 이펙트·대미지 숫자, 상태이상·증기압·보스 폭주, 결과·레벨업 창, 승리 후 필드 복귀
- **마을 굴뚝거리** (`data/maps3d/chimney_ward.json`, 건물 `src3d/buildings.py`): 베르단 숲 서쪽 선착장 ↔ 알바트로스호.
  벽돌·회벽·목조 집, 시계탑, 굴뚝 연기, 증기 파이프, 가로등, 간판. **무기점**(대장장이 브론), **잡화점**(모르간: 소모품·방어구·장신구),
  **여관**(마사: 레벨에 비례한 숙박비로 전원 회복)
- **장비** (`data/equipment.json` ← `tools/data/make_equipment.py`, 규칙 `src/systems/equipment.py`): 무기 30·방어구 26·장신구 14,
  소모품 12종. 상점 물건은 단계(1~6)별로 진행·레벨에 따라 입고(잠긴 것은 "입고 예정"). 메뉴 → 장비에서 능력치 변화 미리보기.
  무기 그림은 `tools/art/gen_equipment.py` 가 그리고, 주인공 그림에서 원래 무기를 지운 몸(`*_body.png`) 위에
  `data/weapon_pose.json` 자세로 붙여 필드·전투·메뉴에서 **장착한 무기가 실제로 보인다**
- **보물상자** 14개 (상점에 없는 무기·방어구·장신구·만능 엘릭서·열쇠 아이템), 열면 뚜껑이 열리고 플래그로 기억
- **특수 이벤트 '잊힌 서약의 시련'**: 세 맵의 상자에서 서약의 인장 조각 3개를 모아 고목의 요람 동쪽 제단으로 →
  보스 '서약의 망령' → 최강 무기(서약검 오스카·천년의 공명봉 엘레이온·알바트로스 노바)와 최강 갑옷 3벌
- **캐릭터 동작** (`src3d/shaders.py` 종이 인형 리그): 일러스트 한 장을 격자 메시 + 정점 셰이더로 움직임 —
  걸을 때 다리를 번갈아 들고 몸이 출렁이며 앞으로 숙임, 좌우 전환은 종이를 뒤집듯 회전, 발소리·흙먼지
- **전투 연출**: 웅크림 → 돌진(잔상) → 내리치기/사격 반동/마법 부유, 피격 넉백·흔들림·번쩍임, 빈사 시 무릎, 쓰러짐, 승리 점프.
  스킬은 단계(1~6)가 높을수록 화려함 — 3단계부터 마법진·기 모으기·카메라 접근·충격파, 5~6단계는 컷인·화면 암전·
  빛기둥·슬로 모션. 치명타(아군 12%)는 공격 전에 판정해 반신 컷인 "CRITICAL!" + 히트스톱 + 큰 넉백
- 반투명 양피지 대화창 + 우측 하단 대형 스탠딩 일러스트(감정별, 인물이 바뀌면 슬라이드 인), 맵 이름 배너
- 맵 정의: `data/maps3d/*.json`, 그래픽: `python tools/art/gen_hd_chars.py`, `python tools/art/gen_textures3d.py`
- **SD 캐릭터 일러스트 교체**: `data/art_prompts/field_chars.json` 의 프롬프트로 1024x1024 흰 배경 이미지를 생성해
  `assets_src/characters/field/<id>.png` 에 넣고 `python tools/art/prepare_field_chars.py` 실행
  (rembg `isnet-anime` 모델로 누끼 → 흰 테두리 색 복원 → 다리 사이 같은 배경 구멍 제거 → 여백 자르기 →
  `assets/characters/field/<id>.png`). 이미지가 있는 캐릭터는 자동으로 전신 일러스트 빌보드로, 없는 캐릭터는 기존 시트 스프라이트로 표시된다.
  도구 설치: `pip install "rembg[cpu]"` (게임 실행에는 필요 없음)
- 자동 테스트: `python main.py --shots 폴더` — 타이틀 → 새 게임 → 이벤트 → 전투 → 메뉴·아이템·저장 → 맵 이동 → 보스 이벤트 →
  타이틀 → 이어하기까지 실제 게임 루프로 진행하며 12개 항목 점검 + 스크린샷 (화면 없는 리눅스에서는 `xvfb-run -a`)
- 몬스터 일러스트: `assets_src/monsters/<적 id>.png` → `python tools/art/prepare_field_chars.py --src assets_src/monsters --out assets/characters/monster --crop-bottom 0.04` (없으면 예전 2D 그림)
- 조명은 `src3d/shaders.py` 의 자체 셰이더(방향광·환경광·안개). ursina 기본 그림자 셰이더는 일부 드라이버에서 크래시가 나서 쓰지 않는다.

## 2D 버전에서 구현된 시스템 (`main2d.py`)
- **필드**: 아이소메트릭 타일맵, 블록을 쌓은 건물, 깊이 정렬, 에테르 가로등 광원, 어두운 맵 조명, 맵 이동, NPC 배회
- **대화**: 타자기 효과, 감정별 초상화 일러스트(주인공), NPC 는 도트 초상화, 대사는 `data/story.json` 에서 읽음
- **ATB 전투**: 속도 기반 게이지, 웨이트 모드 명령 입력(공격/스킬/방어/아이템/도주), 약점·내성·치명타,
  상태이상(화상·정지·실명·도발·방어↑·약점노출), 루크 증기압 게이지(MAX 시 1.5배 → 다음 턴 과열), 보스 폭주 패턴
- **이펙트**: 가산 합성 파티클·링·빔·빛기둥·시계 정지 등 스킬별 연출, 대미지 숫자, 피격 흔들림
- **성장**: 경험치, 레벨업(능력치 상승·스킬 습득 표시), 결과 화면
- **세이브/로드**: 필드 메뉴(X) → 저장 (슬롯 3개, 덮어쓰기 확인), 타이틀 → 이어하기.
  저장 위치: Windows `%APPDATA%\\Arcturus_RPG\\saves`, macOS `~/Library/Application Support/Arcturus_RPG/saves`,
  Linux `~/.local/share/Arcturus_RPG/saves` (`ARCTURUS_SAVE_DIR` 로 변경 가능)
- **사운드**: 직접 작곡해 FluidSynth + FluidR3_GM 오케스트라 사운드폰트로 렌더링한 BGM 8곡(title/town/field/battle/tense/sad/mystery/epic, `.mid` 원본 동봉)과 효과음 22종 (`assets/bgm`, `assets/sfx`)

## 폴더
```
main.py                 3D 본편 진입점 (자동 테스트 --shots, 빌드 검증 --smoke)
main2d.py               이전 2D 버전 진입점
src3d/game.py           3D 필드·맵 이동·이벤트·카메라·대화창
src3d/battle3d.py       3D 전투 연출·UI
src3d/menu3d.py         필드 메뉴·타이틀 화면
src/systems/battle_core.py  전투 규칙 (2D/3D 공용)
src/systems/save.py     세이브/로드 (2D/3D 공용)
data/maps3d/*.json      3D 맵 (지형·길·언덕·거목·NPC·출구·이벤트·인카운트)
src/engine              게임 루프·장면 스택·입력, 리소스 로더·오디오
src/scenes              title / field / dialogue / battle / menu
src/entities/party.py   캐릭터·레벨업·인벤토리
src/systems/effects.py  스킬 이펙트
src/ui/widgets.py       9-slice 창, 게이지, 톱니 커서, 목록 메뉴
data/story.json         세계관·인물·스토리·NPC 대사·아트 방향
data/battle.json        전투 수치·적·인카운트·아이템
data/maps/*.json        맵 (바닥 영역, 건물, 소품, NPC, 출구, 인카운트, 보스)
tools/art               도트 그래픽 생성 / 일러스트 후처리(누끼·리사이즈)
tools/audio             BGM·효과음 합성
tools/autotest.py       자동 플레이 테스트
```

## 에셋 다시 만들기
```bash
python tools/art/gen_pixel_art.py      # 캐릭터 스프라이트·타일·블록·소품
python tools/art/process_assets.py     # assets_src/raw 의 일러스트 → assets/images
python tools/audio/compose_orchestra.py  # 오케스트라 BGM 8곡(assets/bgm)·효과음(assets/sfx), FluidSynth + FluidR3_GM 필요
```

## 테스트
```bash
python tools/autotest.py               # 화면 없이 타이틀~보스까지 자동 플레이, saves/autotest/ 에 스크린샷
```

## 라이선스 메모
- 폰트: Galmuri (SIL OFL 1.1, `assets/fonts/OFL-Galmuri.md`), 나눔명조·나눔고딕 (SIL OFL 1.1, `assets/fonts/OFL-Nanum.txt`)
- 사운드폰트: FluidR3_GM (MIT) — 렌더링에만 사용, 저장소에는 결과 OGG 만 포함
- 그 외 그래픽·사운드는 이 저장소의 스크립트로 생성한 것

## 실행 파일(.exe) 빌드
파이썬이 없는 PC 에서도 더블클릭으로 실행되는 단일 실행 파일을 만든다. 모든 그래픽·사운드·폰트·데이터가 포함된다.

- **자동 (권장)**: 이 저장소에 push 하면 GitHub Actions(`.github/workflows/build-windows.yml`)가 Windows 에서
  `Arcturus_RPG.exe` 를 빌드하고 실행 검증까지 한 뒤, 실행 결과 페이지의 Artifacts 에 `Arcturus_RPG-windows` 로 올린다.
- **직접 (Windows PC)**:
  ```bat
  pip install pygame-ce Pillow pyinstaller
  python tools\build_exe.py
  ```
  결과: `dist\Arcturus_RPG.exe`

PyInstaller 는 크로스 컴파일을 지원하지 않으므로 `.exe` 는 반드시 Windows 에서 빌드해야 한다
(리눅스·macOS 에서 같은 명령을 실행하면 그 OS 용 실행 파일이 나온다).
실행 중 오류가 나면 실행 파일 옆에 `Arcturus_RPG_error.log` 가 남는다.
