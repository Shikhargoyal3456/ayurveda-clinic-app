import { useRef } from 'react';
import { motion, type MotionValue, useScroll, useTransform } from 'framer-motion';

interface AnimatedTextProps {
  text: string;
  className?: string;
}

interface AnimatedCharacterProps {
  char: string;
  index: number;
  total: number;
  progress: MotionValue<number>;
}

function AnimatedCharacter({ char, index, total, progress }: AnimatedCharacterProps) {
  const opacity = useTransform(progress, [index / total, (index + 1) / total], [0.2, 1]);
  const displayChar = char === ' ' ? '\u00A0' : char;

  return (
    <span className="relative inline-block">
      <span className="invisible">{displayChar}</span>
      <motion.span className="absolute inset-0" style={{ opacity }}>
        {displayChar}
      </motion.span>
    </span>
  );
}

export default function AnimatedText({ text, className = '' }: AnimatedTextProps) {
  const ref = useRef<HTMLParagraphElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start 0.8', 'end 0.2'],
  });

  const characters = text.split('');

  return (
    <p ref={ref} className={`relative ${className}`}>
      {characters.map((char, i) => (
        <AnimatedCharacter
          key={`${char}-${i}`}
          char={char}
          index={i}
          total={characters.length}
          progress={scrollYProgress}
        />
      ))}
    </p>
  );
}
