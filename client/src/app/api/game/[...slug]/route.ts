import { NextRequest, NextResponse } from 'next/server';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_KEY = process.env.API_KEY; // Server-side only, not visible to client

// Handle all game-related API calls
export async function GET(
  request: NextRequest,
  { params }: { params: { slug: string[] } }
) {
  return handleRequest(request, params.slug, 'GET');
}

export async function POST(
  request: NextRequest,
  { params }: { params: { slug: string[] } }
) {
  return handleRequest(request, params.slug, 'POST');
}

export async function PUT(
  request: NextRequest,
  { params }: { params: { slug: string[] } }
) {
  return handleRequest(request, params.slug, 'PUT');
}

async function handleRequest(
  request: NextRequest,
  slug: string[],
  method: string
) {
  try {
    // Reconstruct the path
    const path = slug.join('/');
    const url = new URL(request.url);
    const searchParams = url.searchParams.toString();
    const fullPath = `${API_URL}/${path}${searchParams ? `?${searchParams}` : ''}`;
    
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    
    // Forward authorization header if present
    const authHeader = request.headers.get('Authorization');
    if (authHeader) {
      headers['Authorization'] = authHeader;
    }
    
    // Forward Accept header for streaming endpoints
    const acceptHeader = request.headers.get('Accept');
    if (acceptHeader) {
      headers['Accept'] = acceptHeader;
    }
    
    // Add API key if configured (server-side only)
    if (API_KEY) {
      headers['X-API-Key'] = API_KEY;
    }
    
    let body;
    if (method !== 'GET') {
      try {
        body = await request.json();
      } catch {
        // No body or invalid JSON
      }
    }
    
    const response = await fetch(fullPath, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    
    // Handle streaming responses (like action/stream)
    if (response.headers.get('content-type')?.includes('text/event-stream')) {
      return new NextResponse(response.body, {
        status: response.status,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      });
    }
    
    // Handle regular JSON responses
    const data = await response.json();
    
    if (!response.ok) {
      return NextResponse.json(data, { status: response.status });
    }
    
    return NextResponse.json(data);
  } catch (error) {
    console.error('Game API proxy error:', error);
    return NextResponse.json(
      { detail: 'Internal server error' },
      { status: 500 }
    );
  }
}
