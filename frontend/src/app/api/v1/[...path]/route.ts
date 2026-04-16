import { NextRequest, NextResponse } from 'next/server';
import { cookies } from 'next/headers';

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
  
  // 1. Handle Authorization: Prioritize cookies for HttpOnly security, fallback to header
  const cookieStore = await cookies();
  const accessToken = cookieStore.get('sd_access_token')?.value;
  const authHeader = request.headers.get('authorization');
  
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  } else if (authHeader) {
    headers.set('Authorization', authHeader);
  }

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
    
    // Intercept specific auth endpoints to set HttpOnly cookies
    const pathStr = path.join('/');
    const isTokenResp = pathStr === 'accounts/auth/token' || 
                        pathStr === 'accounts/auth/token/refresh' ||
                        pathStr === 'accounts/profile/become-seller';

    const outHeaders = new Headers(res.headers);
    outHeaders.delete('Access-Control-Allow-Origin');
    outHeaders.delete('Access-Control-Allow-Credentials');

    // If we need to intercept tokens, we MUST NOT pass res.body to NextResponse yet,
    // because reading it later (even with clone()) causes lock issues in Next.js.
    // Instead, we consume it into a buffer for these specific endpoints.
    if (res.ok && isTokenResp) {
      const buffer = await res.arrayBuffer();
      const response = new NextResponse(buffer, {
        status: res.status,
        statusText: res.statusText,
        headers: outHeaders,
      });

      try {
        const text = new TextDecoder().decode(buffer);
        const dataRes = JSON.parse(text);
        const access = dataRes.access;
        const refresh = dataRes.refresh;

        if (access) {
          response.cookies.set('sd_access_token', access, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'lax',
            path: '/',
            maxAge: 60 * 60, // 1 hour
          });
        }
        if (refresh) {
          response.cookies.set('sd_refresh_token', refresh, {
            httpOnly: true,
            secure: process.env.NODE_ENV === 'production',
            sameSite: 'lax',
            path: '/',
            maxAge: 30 * 24 * 60 * 60, // 30 days
          });
        }
      } catch (err) {
        console.warn('[api proxy] Failed to parse token response as JSON:', err);
      }
      return response;
    }

    // Default: Stream the response body
    const response = new NextResponse(res.body, {
      status: res.status,
      statusText: res.statusText,
      headers: outHeaders,
    });

    // Handle logout: Clear cookies
    if (pathStr === 'accounts/auth/logout') {
      response.cookies.delete('sd_access_token');
      response.cookies.delete('sd_refresh_token');
    }

    return response;
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

