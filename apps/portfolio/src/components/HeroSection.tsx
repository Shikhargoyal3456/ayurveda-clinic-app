import ContactButton from './ContactButton';
import FadeIn from './FadeIn';
import Magnet from './Magnet';

export default function HeroSection() {
  const navLinks = ['About', 'Price', 'Projects', 'Contact'];

  return (
    <section className="relative flex h-screen flex-col overflow-x-clip" id="contact">
      <FadeIn x={0} y={-20} delay={0} duration={0.7}>
        <nav className="flex items-center justify-between px-6 pt-6 md:px-10 md:pt-8">
          {navLinks.map((link) => (
            <a
              key={link}
              href={`#${link === 'Price' ? 'services' : link.toLowerCase()}`}
              className="text-sm font-medium uppercase tracking-wider text-[#D7E2EA] transition-opacity duration-200 hover:opacity-70 md:text-lg lg:text-[1.4rem]"
            >
              {link}
            </a>
          ))}
        </nav>
      </FadeIn>

      <FadeIn x={0} y={40} delay={0.15} duration={0.8}>
        <div className="mt-6 w-full overflow-hidden sm:mt-4 md:-mt-5">
          <h1 className="hero-heading w-full whitespace-nowrap text-[14vw] font-black uppercase leading-none tracking-normal sm:text-[15vw] md:text-[16vw] lg:text-[17.5vw]">
            Hi, i&apos;m jack
          </h1>
        </div>
      </FadeIn>

      <div className="flex flex-1 items-end justify-between px-6 pb-7 sm:pb-8 md:px-10 md:pb-10">
        <FadeIn x={0} y={20} delay={0.35} duration={0.7}>
          <p className="max-w-[160px] text-[clamp(0.75rem,1.4vw,1.5rem)] font-light uppercase leading-snug tracking-wide text-[#D7E2EA] sm:max-w-[220px] md:max-w-[260px]">
            a 3d creator driven by crafting striking and unforgettable projects
          </p>
        </FadeIn>

        <FadeIn x={0} y={20} delay={0.5} duration={0.7}>
          <ContactButton />
        </FadeIn>
      </div>

      <FadeIn
        x={0}
        y={30}
        delay={0.6}
        duration={0.8}
        className="absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-1/2 sm:bottom-0 sm:top-auto sm:translate-y-0"
      >
        <Magnet padding={150} strength={3}>
          <img
            src="https://shrug-person-78902957.figma.site/_components/v2/d24c01ad3a56fc65e942a1f501eb73db42d7cf9a/Rectangle_40443.81459862.png"
            alt="Jack Portrait"
            className="w-[280px] object-cover sm:w-[360px] md:w-[440px] lg:w-[520px]"
          />
        </Magnet>
      </FadeIn>
    </section>
  );
}
