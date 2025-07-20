# Run in day

- first commit

## 환경 변수 설정

1. `.env.example` 파일 참고해서 `.env` 파일 생성하기

    ```bash
    cp .env.example .env
    ```

    - 입력하면 example파일 기반으로 env 파일 만들어짐. 그 뒤에 api키나 해당 비밀번호 같은거 입력하면 됨.
    - env파일 git에 올리면 안되는건 다들 아실거구용

## Docker

- 먼저 env 파일 다 만들고 Docker 깝니다. docker desktop 켜서 docker engine 활성화 시키고! 보통 docker 실행하면 저절로 엔진 켜져요. 그리고 나서 bash 창에

    ```bash
    docker-compose up --build   # 이거 입력하면 알아서 빌드해서 이미지 생성, 컨테이너 생성 다해서 실행됩니다. (--build 빼면 그냥 컨테이너 키는겁니다.)
    docker-compose down         # 컨테이너 끄기
    ```

- 다른 커맨드는 찾아보시길..
- db 연결은 저번에 한 그대로 하면되는데, 제 컴퓨터는 5432 포트는 쓰고 있어서 로컬은 5433 설정해놨습니다. 로컬 연결이랑 Docker DB 연결이랑 달라서
디비버에서 새 데이터베이스 연결하고, 포트 5433으로 생성해야합니다. 모르는건 mm 하십쇼. 솔직히 만나서 하는게 최고라 다음주 주말에 더 상세히 알려드리죠.