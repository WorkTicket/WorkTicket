import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { blogPosts, getPost } from "@/lib/blog";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export async function generateStaticParams() {
  return blogPosts.map((post) => ({ slug: post.slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) return { title: "Post Not Found" };
  return {
    title: post.title,
    description: post.description,
  };
}

export default async function BlogPostPage({ params }: PageProps) {
  const { slug } = await params;
  const post = getPost(slug);
  if (!post) notFound();

  return (
    <article className="section-padding">
      <div className="container-content mx-auto max-w-3xl">
        <Link href="/blog" className="text-sm font-medium text-brand-600 hover:underline">
          &larr; Back to Blog
        </Link>
        <header className="mt-6">
          <time dateTime={post.date} className="text-sm text-slate-500">
            {new Date(post.date).toLocaleDateString("en-US", {
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </time>
          <h1 className="mt-2 text-4xl font-bold tracking-tight text-slate-900">{post.title}</h1>
          <p className="mt-4 text-lg text-slate-600">{post.description}</p>
          <p className="mt-2 text-sm text-slate-500">
            By {post.author} · {post.readingTime}
          </p>
        </header>
        <div className="prose-marketing mt-10 space-y-4 text-slate-700">
          <p>
            This is a placeholder article. Full MDX blog content can be added in{" "}
            <code className="rounded bg-slate-100 px-1.5 py-0.5 text-sm">content/blog/</code> as
            your content strategy grows.
          </p>
          <p>
            WorkTicket helps skilled trades businesses manage the full job lifecycle — from first
            customer contact through estimate approval, scheduling, field updates, and invoicing.
          </p>
        </div>
      </div>
    </article>
  );
}
