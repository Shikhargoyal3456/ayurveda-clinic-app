export interface Project {
  id: string;
  title: string;
  category: 'Client' | 'Personal';
  images: {
    col1: string[];
    col2: string;
  };
}
