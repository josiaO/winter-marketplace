import { redirect } from 'next/navigation';

export const dynamic = 'force-dynamic';

type SearchPageProps = {
  searchParams: Record<string, string | string[] | undefined>;
};

export default function Page({ searchParams }: SearchPageProps) {
  const raw = searchParams.q;
  const q = Array.isArray(raw) ? raw[0] : raw;
  const trimmed = typeof q === 'string' ? q.trim() : '';
  if (trimmed) {
    redirect(`/marketplace?q=${encodeURIComponent(trimmed)}`);
  }
  redirect('/marketplace');
}
