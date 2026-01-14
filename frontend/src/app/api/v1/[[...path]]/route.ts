import { NextRequest, NextResponse } from 'next/server';

// This is a runtime API route that proxies requests to the backend.
// It reads API_URL at runtime (not build time), so it works reliably
// with environment variables set in Railway.

const getApiUrl = () => {
  // Check environment variables at RUNTIME
  const apiUrl = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
  console.log('[API Proxy] Using backend URL:', apiUrl);
  return apiUrl;
};

async function proxyRequest(request: NextRequest, params: { path?: string[] }) {
  const apiUrl = getApiUrl();
  const path = params.path?.join('/') || '';
  const targetUrl = `${apiUrl}/api/v1/${path}${request.nextUrl.search}`;
  
  console.log(`[API Proxy] ${request.method} ${targetUrl}`);
  
  // Get headers from the original request
  const headers = new Headers();
  request.headers.forEach((value, key) => {
    // Don't forward host header to avoid issues
    if (key.toLowerCase() !== 'host') {
      headers.set(key, value);
    }
  });
  
  try {
    let body = null;
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      // For POST/PUT/PATCH, forward the body
      body = await request.text();
    }
    
    const response = await fetch(targetUrl, {
      method: request.method,
      headers,
      body,
    });
    
    // Get response headers
    const responseHeaders = new Headers();
    response.headers.forEach((value, key) => {
      responseHeaders.set(key, value);
    });
    
    // Return the proxied response
    const responseBody = await response.text();
    return new NextResponse(responseBody, {
      status: response.status,
      statusText: response.statusText,
      headers: responseHeaders,
    });
  } catch (error) {
    console.error('[API Proxy] Error:', error);
    return NextResponse.json(
      { error: 'Failed to proxy request', details: String(error) },
      { status: 500 }
    );
  }
}

export async function GET(request: NextRequest, { params }: { params: { path?: string[] } }) {
  return proxyRequest(request, params);
}

export async function POST(request: NextRequest, { params }: { params: { path?: string[] } }) {
  return proxyRequest(request, params);
}

export async function PUT(request: NextRequest, { params }: { params: { path?: string[] } }) {
  return proxyRequest(request, params);
}

export async function PATCH(request: NextRequest, { params }: { params: { path?: string[] } }) {
  return proxyRequest(request, params);
}

export async function DELETE(request: NextRequest, { params }: { params: { path?: string[] } }) {
  return proxyRequest(request, params);
}
