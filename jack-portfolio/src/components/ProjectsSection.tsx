import { useRef } from 'react';
import { motion, useScroll, useTransform } from 'framer-motion';
import type { Project } from '../types';
import LiveProjectButton from './LiveProjectButton';

const projects: Project[] = [
  {
    id: '01',
    title: 'Nextlevel Studio',
    category: 'Client',
    images: {
      col1: [
        'https://images.higgs.ai/?default=1&output=webp&url=https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20260412_055344_5eff02e0-87a5-41ce-b64f-eb08da8f33db.png&w=1280&q=85',
        'https://images.higgs.ai/?default=1&output=webp&url=https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20260412_055431_11d841fd-8b41-46a5-82e4-b04f2407a7d8.png&w=1280&q=85',
      ],
      col2: 'https://images.higgs.ai/?default=1&output=webp&url=https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20260412_055451_e317bf2d-28d4-48cc-86b0-6f72f25b6327.png&w=1280&q=85',
    },
  },
  {
    id: '02',
    title: 'Aura Brand Identity',
    category: 'Personal',
    images: {
      col1: [
        'https://images.higgs.ai/?default=1&output=webp&url=https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20260412_055654_911201c5-36d9-4bc6-bac7-331adfce159f.png&w=1280&q=85',
        'https://images.higgs.ai/?default=1&output=webp&url=https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20260412_055723_5ceda0b8-d9c2-4665-b2e3-83ba19ba76d1.png&w=1280&q=85',
      ],
      col2: 'https://images.higgs.ai/?default=1&output=webp&url=https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20260412_055753_adc5dcbd-a8e6-49c0-b43a-9b030d835cea.png&w=1280&q=85',
    },
  },
  {
    id: '03',
    title: 'Solaris Digital',
    category: 'Client',
    images: {
      col1: [
        'https://images.higgs.ai/?default=1&output=webp&url=https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20260412_055759_963cfb0b-4bd1-4b0f-9d0a-09bd6cf95b2f.png&w=1280&q=85',
        'https://images.higgs.ai/?default=1&output=webp&url=https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20260412_060108_438f781a-9846-4dcc-89ab-c4e6cb830f5b.png&w=1280&q=85',
      ],
      col2: 'https://images.higgs.ai/?default=1&output=webp&url=https%3A%2F%2Fd8j0ntlcm91z4.cloudfront.net%2Fuser_38xzZboKViGWJOttwIXH07lWA1P%2Fhf_20260412_055818_9d062121-ad7e-46b9-999a-1a6a692ef1ee.png&w=1280&q=85',
    },
  },
];

function ProjectShowcase({ project, index }: { project: Project; index: number }) {
  const ref = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start end', 'end start'],
  });
  const yLeft = useTransform(scrollYProgress, [0, 1], [index % 2 === 0 ? 50 : -30, -60]);
  const yRight = useTransform(scrollYProgress, [0, 1], [index % 2 === 0 ? -40 : 40, 70]);

  return (
    <section
      ref={ref}
      className="grid min-h-screen gap-8 border-t border-white/15 px-5 py-16 sm:px-8 md:grid-cols-[0.9fr_1.1fr] md:px-10 md:py-24"
    >
      <div className="flex flex-col justify-between gap-8">
        <div>
          <p className="mb-3 text-xl font-black text-[#D7E2EA]/40 sm:text-3xl">{project.id}</p>
          <h3 className="max-w-[720px] text-[clamp(2.5rem,7vw,7.5rem)] font-black uppercase leading-[0.92] text-[#D7E2EA]">
            {project.title}
          </h3>
          <p className="mt-5 text-lg font-light uppercase tracking-widest text-[#D7E2EA]/70">
            {project.category}
          </p>
        </div>
        <LiveProjectButton className="w-fit" />
      </div>

      <div className="grid gap-4 sm:grid-cols-[0.85fr_1.15fr]">
        <motion.div style={{ y: yLeft }} className="flex flex-col gap-4">
          {project.images.col1.map((src, imageIndex) => (
            <img
              key={src}
              src={src}
              alt={`${project.title} preview ${imageIndex + 1}`}
              className="aspect-[4/3] w-full rounded-2xl object-cover"
              loading="lazy"
            />
          ))}
        </motion.div>
        <motion.img
          src={project.images.col2}
          alt={`${project.title} hero preview`}
          className="h-full min-h-[360px] rounded-2xl object-cover"
          loading="lazy"
          style={{ y: yRight }}
        />
      </div>
    </section>
  );
}

export default function ProjectsSection() {
  return (
    <section id="projects" className="bg-[#0C0C0C] py-20">
      <div className="px-5 sm:px-8 md:px-10">
        <h2 className="hero-heading mb-14 text-[clamp(3rem,12vw,160px)] font-black uppercase leading-none tracking-normal">
          Projects
        </h2>
      </div>
      {projects.map((project, index) => (
        <ProjectShowcase key={project.id} project={project} index={index} />
      ))}
    </section>
  );
}
