import { NextRequest, NextResponse } from 'next/server';

function djangoOrigin(): string {
  return (
    process.env.INTERNAL_API_URL ||
    process.env.API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    'http://127.0.0.1:8000'
  ).replace(/\/$/, '');
}

function buildUpstreamUrl(pathSegments: string[], search: string): string {
  const base = djangoOrigin();
  const suffix = pathSegments.length ? `${pathSegments.join('/')}/` : '';
  return `${base}/api/v1/${suffix}${search}`;
}

async function proxy(request: NextRequest, context: { params: Promise<{ path?: string[] }> }) {
  const { path = [] } = await context.params;
  const search = request.nextUrl.search || '';
  const upstream = buildUpstreamUrl(path, search);

  const headers = new Headers();
  const auth = request.headers.get('authorization');
  if (auth) headers.set('Authorization', auth);
  const lang = request.headers.get('accept-language');
  if (lang) headers.set('Accept-Language', lang);
  const contentType = request.headers.get('content-type');
  if (contentType) headers.set('Content-Type', contentType);

  const method = request.method;
  const init: RequestInit = { method, headers, redirect: 'manual' };

  if (method !== 'GET' && method !== 'HEAD') {
    const body = await request.arrayBuffer();
    if (body.byteLength > 0) init.body = body;
  }

  try {
    const res = await fetch(upstream, init);
    const outHeaders = new Headers(res.headers);
    outHeaders.delete('Access-Control-Allow-Origin');
    outHeaders.delete('Access-Control-Allow-Credentials');

    return new NextResponse(res.body, {
      status: res.status,
      statusText: res.statusText,
      headers: outHeaders,
    });
  } catch (e) {
    console.error('[api/v1 proxy] upstream fetch failed:', upstream, e);
    return NextResponse.json(
      {
        detail:
          'Unable to reach the API server. Start Django or set NEXT_PUBLIC_API_URL / INTERNAL_API_URL.',
        upstream,
      },
      { status: 502 },
    );
  }
}

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;

