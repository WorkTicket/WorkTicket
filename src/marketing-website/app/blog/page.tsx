import type { Metadata } from "next";
import Link from "next/link";
import { blogPosts } from "@/lib/blog";

export const metadata: Metadata = {
  title: "Blog",
  description: "Tips, guides, and updates for skilled trades businesses using WorkTicket.",
};

export default function BlogPage() {
  return (
    <section className="section-padding">
      <div className="container-content mx-auto max-w-3xl">
        <h1 className="text-4xl font-bold tracking-tight text-slate-900">Blog</h1>
        <p className="mt-4 text-slate-600">
          Practical advice for running a more efficient trades business.
        </p>

        <div className="mt-12 space-y-8">
          {blogPosts.map((post) => (
            <article key={post.slug} className="border-b border-surface-border pb-8">
              <Link href={`/blog/${post.slug}`} className="group block">
                <time dateTime={post.date} className="text-sm text-slate-500">
                  {new Date(post.date).toLocaleDateString("en-US", {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })}
                </time>
                <h2 className="mt-2 text-2xl font-semibold text-slate-900 group-hover:text-brand-600">
                  {post.title}
                </h2>
                <p className="mt-2 text-slate-600">{post.description}</p>
                <p className="mt-3 text-sm text-slate-500">{post.readingTime}</p>
              </Link>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
