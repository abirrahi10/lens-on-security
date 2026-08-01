import { defineCollection, z } from 'astro:content';

const blog = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    dek: z.string(),
    date: z.string(),
    readTime: z.string(),
    tags: z.array(z.string()).min(1),
    images: z.array(z.object({
      src: z.string(),
      alt: z.string(),
    })).min(1),
    sources: z.array(z.string().url()).optional(),
    draft: z.boolean().default(false),
  }),
});

export const collections = { blog };
