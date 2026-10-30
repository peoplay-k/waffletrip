// 발행된 기사의 지면 주소. 화면(편집기·목록)과 서버(발행 상태)가 같이 쓴다.
// 지면의 긴 주소는 제목 slug 가 들어가 여기서 똑같이 만들기 어렵다. 그래서 파이프라인이
// 기사마다 만들어 두는 짧은 주소 /지역/발행id 앞 8자/ 를 쓴다(src/render/site.py short_url).
// 발행 상태가 아니면(작성중·내림 등) 지면에 없으므로 빈 값.

export function articleSiteUrl(front, base = 'https://waffletrip.com') {
  if (!front || !front.published_id || front.status !== 'published') return '';
  const seg = (s) => String(s || '').replace(/[^A-Za-z0-9_-]/g, '');
  const region = front.channel === 'ent' ? 'ent' : (seg(front.region) || 'etc');
  const ident = seg(front.published_id).slice(0, 8) || '0';
  return `${String(base || 'https://waffletrip.com').replace(/\/+$/, '')}/${region}/${ident}/`;
}
