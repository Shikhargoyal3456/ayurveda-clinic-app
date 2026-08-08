import { useEffect } from 'react';
import AboutSection from './components/AboutSection';
import HeroSection from './components/HeroSection';
import MarqueeSection from './components/MarqueeSection';
import ProjectsSection from './components/ProjectsSection';
import ServicesSection from './components/ServicesSection';

function App() {
  useEffect(() => {
    document.title = 'Jack - 3D Creator';
  }, []);

  return (
    <div className="overflow-x-clip">
      <HeroSection />
      <MarqueeSection />
      <AboutSection />
      <ServicesSection />
      <ProjectsSection />
    </div>
  );
}

export default App;
