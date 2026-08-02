import { AmbientGradient } from './AmbientGradient'
import { ArchitecturalPipeline } from './ArchitecturalPipeline'

export function LandingBackground() {
  return (
    <div className="fixed inset-0 z-[-10] bg-[#FCFBF9]">
      <AmbientGradient />

      {/* 3D Focal Architectural Background */}
      <ArchitecturalPipeline />

      {/* Very Subtle Noise Texture Overlay to prevent gradient banding and add a paper-like feel */}
      <div
        className="absolute inset-0 opacity-[0.015] mix-blend-multiply pointer-events-none z-10"
        style={{
          backgroundImage: 'url("data:image/svg+xml,%3Csvg viewBox=%220 0 200 200%22 xmlns=%22http://www.w3.org/2000/svg%22%3E%3Cfilter id=%22noiseFilter%22%3E%3CfeTurbulence type=%22fractalNoise%22 baseFrequency=%220.65%22 numOctaves=%223%22 stitchTiles=%22stitch%22/%3E%3C/filter%3E%3Crect width=%22100%25%22 height=%22100%25%22 filter=%22url(%23noiseFilter)%22/%3E%3C/svg%3E")'
        }}
      />
    </div>
  )
}
