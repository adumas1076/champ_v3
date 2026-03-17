/**
 * useAvatar — Detects and provides the avatar participant's video track.
 *
 * Scans remote participants in the LiveKit room for one that:
 * 1. Has a published video track (Camera source)
 * 2. Matches avatar identity patterns (avatar, liveavatar, champ-avatar, etc.)
 *
 * Returns the video track and participant info so the UI can render
 * a <video> element instead of a static image.
 *
 * Pattern: Skipper V5 useAvatar hook (reference/skipper_app_v5-main)
 */

import { useState, useEffect, useCallback } from "react";
import {
  useRoomContext,
  useRemoteParticipants,
} from "@livekit/components-react";
import {
  RemoteParticipant,
  RemoteTrackPublication,
  Track,
  RoomEvent,
} from "livekit-client";

// Participant identity patterns that indicate an avatar
const AVATAR_PATTERNS = [
  "avatar",
  "liveavatar",
  "champ-avatar",
  "heygen",
  "flashhead",
  "simli",
  "digital-human",
];

interface AvatarState {
  /** The avatar video track (null if no avatar detected) */
  videoTrack: RemoteTrackPublication | null;
  /** The avatar participant */
  participant: RemoteParticipant | null;
  /** Whether an avatar is present and has video */
  isAvatarActive: boolean;
  /** Whether the avatar is currently speaking (has active audio) */
  isAvatarSpeaking: boolean;
}

export function useAvatar(): AvatarState {
  const room = useRoomContext();
  const remoteParticipants = useRemoteParticipants();
  const [avatarState, setAvatarState] = useState<AvatarState>({
    videoTrack: null,
    participant: null,
    isAvatarActive: false,
    isAvatarSpeaking: false,
  });

  const findAvatar = useCallback(() => {
    if (!remoteParticipants || remoteParticipants.length === 0) {
      return { participant: null, videoTrack: null };
    }

    // Priority 1: Remote participant with a video track
    for (const p of remoteParticipants) {
      const videoTrack = Array.from(p.trackPublications.values()).find(
        (pub) =>
          pub.source === Track.Source.Camera &&
          pub.track &&
          !pub.isMuted
      ) as RemoteTrackPublication | undefined;

      if (videoTrack) {
        return { participant: p as RemoteParticipant, videoTrack };
      }
    }

    // Priority 2: Identity pattern match (avatar may not have published video yet)
    for (const p of remoteParticipants) {
      const identity = (p.identity || "").toLowerCase();
      if (AVATAR_PATTERNS.some((pat) => identity.includes(pat))) {
        const videoTrack = Array.from(p.trackPublications.values()).find(
          (pub) => pub.source === Track.Source.Camera
        ) as RemoteTrackPublication | undefined;
        return {
          participant: p as RemoteParticipant,
          videoTrack: videoTrack || null,
        };
      }
    }

    return { participant: null, videoTrack: null };
  }, [remoteParticipants]);

  // Update avatar state when participants change
  useEffect(() => {
    const { participant, videoTrack } = findAvatar();

    setAvatarState((prev) => {
      if (prev.participant === participant && prev.videoTrack === videoTrack) {
        return prev;
      }
      return {
        videoTrack,
        participant,
        isAvatarActive: !!videoTrack,
        isAvatarSpeaking: prev.isAvatarSpeaking,
      };
    });
  }, [findAvatar]);

  // Listen for track subscribed/unsubscribed events
  useEffect(() => {
    if (!room) return;

    const handleTrackSubscribed = () => {
      const { participant, videoTrack } = findAvatar();
      setAvatarState((prev) => ({
        ...prev,
        videoTrack,
        participant,
        isAvatarActive: !!videoTrack,
      }));
    };

    const handleActiveSpeakers = (speakers: any[]) => {
      setAvatarState((prev) => {
        if (!prev.participant) return prev;
        const isSpeaking = speakers.some(
          (s) => s.identity === prev.participant?.identity
        );
        if (prev.isAvatarSpeaking === isSpeaking) return prev;
        return { ...prev, isAvatarSpeaking: isSpeaking };
      });
    };

    room.on(RoomEvent.TrackSubscribed, handleTrackSubscribed);
    room.on(RoomEvent.TrackUnsubscribed, handleTrackSubscribed);
    room.on(RoomEvent.TrackPublished, handleTrackSubscribed);
    room.on(RoomEvent.TrackUnpublished, handleTrackSubscribed);
    room.on(RoomEvent.ActiveSpeakersChanged, handleActiveSpeakers);

    return () => {
      room.off(RoomEvent.TrackSubscribed, handleTrackSubscribed);
      room.off(RoomEvent.TrackUnsubscribed, handleTrackSubscribed);
      room.off(RoomEvent.TrackPublished, handleTrackSubscribed);
      room.off(RoomEvent.TrackUnpublished, handleTrackSubscribed);
      room.off(RoomEvent.ActiveSpeakersChanged, handleActiveSpeakers);
    };
  }, [room, findAvatar]);

  return avatarState;
}
