/**
 * 와플트립 편집실 로그인 중개기 (Cloudflare Worker)
 *
 * Decap CMS 가 GitHub 에 글을 쓰려면 OAuth 로그인이 필요한데, GitHub 은
 * 클라이언트 비밀키를 브라우저에 두는 것을 허용하지 않는다. 그래서 아주 작은
 * 중개기가 하나 필요하다. 이 파일이 그것이다.
 *
 * 하는 일은 두 가지뿐이다.
 *   /auth      GitHub 로그인 화면으로 보낸다
 *   /callback  돌아온 코드를 토큰으로 바꿔 CMS 창에 건넨다
 *
 * 비밀키는 Worker 환경변수에만 두고 브라우저로 내려보내지 않는다.
 *
 * ── 배포 ──────────────────────────────────────────────────────
 * 1. GitHub → Settings → Developer settings → OAuth Apps → New
 *      Homepage URL      https://peoplay-k.github.io/waffletrip/
 *      Callback URL      https://<워커주소>/callback
 *    Client ID 와 Client Secret 을 받는다.
 *
 * 2. Cloudflare → Workers → Create → 이 파일 내용을 붙여넣고 Deploy
 *
 * 3. Worker → Settings → Variables 에 두 개를 넣는다 (Secret 으로)
 *      GITHUB_CLIENT_ID
 *      GITHUB_CLIENT_SECRET
 *
 * 4. static/admin/config.yml 의 base_url 을 워커 주소로 바꾸고 배포한다.
 */

const ALLOWED_ORIGIN = "https://peoplay-k.github.io";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/auth") {
      const redirect = `${url.origin}/callback`;
      const authorize = new URL("https://github.com/login/oauth/authorize");
      authorize.searchParams.set("client_id", env.GITHUB_CLIENT_ID);
      authorize.searchParams.set("redirect_uri", redirect);
      authorize.searchParams.set("scope", "repo");
      // 상태값으로 재생 공격을 막는다.
      authorize.searchParams.set("state", crypto.randomUUID());
      return Response.redirect(authorize.toString(), 302);
    }

    if (url.pathname === "/callback") {
      const code = url.searchParams.get("code");
      if (!code) return new Response("code 가 없다", { status: 400 });

      const res = await fetch("https://github.com/login/oauth/access_token", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          client_id: env.GITHUB_CLIENT_ID,
          client_secret: env.GITHUB_CLIENT_SECRET,
          code,
        }),
      });
      const data = await res.json();

      const payload = data.access_token
        ? { token: data.access_token, provider: "github" }
        : { error: data.error_description || "토큰을 받지 못했다" };

      // Decap 은 부모 창으로 메시지를 받아 로그인을 마친다.
      const body = `<!doctype html><meta charset="utf-8"><script>
        (function () {
          function send() {
            window.opener.postMessage(
              'authorization:github:${data.access_token ? "success" : "error"}:' +
              ${JSON.stringify(JSON.stringify(payload))},
              ${JSON.stringify(ALLOWED_ORIGIN)}
            );
          }
          window.addEventListener("message", send, { once: true });
          window.opener.postMessage("authorizing:github", ${JSON.stringify(ALLOWED_ORIGIN)});
        })();
      </script>`;
      return new Response(body, { headers: { "Content-Type": "text/html; charset=utf-8" } });
    }

    return new Response("waffletrip auth", { status: 200 });
  },
};
