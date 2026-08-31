import FadeIn from './FadeIn';

const services = [
  {
    id: '01',
    title: '3D Modeling',
    description:
      'Creation of detailed objects, characters, or environments tailored to specific client needs, ideal for games, products, and visualizations.',
  },
  {
    id: '02',
    title: 'Rendering',
    description:
      'High-quality, photorealistic renders that showcase designs with custom lighting, textures, and materials to bring concepts to life.',
  },
  {
    id: '03',
    title: 'Motion Design',
    description:
      'Dynamic animations and motion graphics that add energy and storytelling to brands, products, and digital experiences.',
  },
  {
    id: '04',
    title: 'Branding',
    description:
      'Crafting cohesive visual identities -- from logos to full brand systems -- that communicate a clear and memorable presence.',
  },
  {
    id: '05',
    title: 'Web Design',
    description:
      'Designing clean, modern, and conversion-focused websites with attention to layout, typography, and user experience.',
  },
];

export default function ServicesSection() {
  return (
    <section
      id="services"
      className="rounded-t-[40px] bg-white px-5 py-20 sm:rounded-t-[50px] sm:px-8 sm:py-24 md:rounded-t-[60px] md:px-10 md:py-32"
    >
      <h2 className="mb-16 text-center text-[clamp(3rem,12vw,160px)] font-black uppercase text-[#0C0C0C] sm:mb-20 md:mb-28">
        Services
      </h2>

      <div className="mx-auto flex max-w-5xl flex-col">
        {services.map((service, index) => (
          <FadeIn
            key={service.id}
            x={0}
            y={30}
            delay={index * 0.1}
            duration={0.7}
            className={`flex flex-col items-start gap-2 border-b border-[rgba(12,12,12,0.15)] py-8 sm:flex-row sm:gap-6 sm:py-10 md:py-12 ${
              index === services.length - 1 ? 'border-b-0' : ''
            }`}
          >
            <span className="text-[clamp(3rem,10vw,140px)] font-black leading-none text-[#0C0C0C] sm:min-w-[120px] md:min-w-[160px]">
              {service.id}
            </span>
            <div className="flex-1">
              <h3 className="text-[clamp(1rem,2.2vw,2.1rem)] font-medium uppercase text-[#0C0C0C]">
                {service.title}
              </h3>
              <p className="max-w-2xl text-[clamp(0.85rem,1.6vw,1.25rem)] font-light leading-relaxed text-[#0C0C0C] opacity-60">
                {service.description}
              </p>
            </div>
          </FadeIn>
        ))}
      </div>
    </section>
  );
}
