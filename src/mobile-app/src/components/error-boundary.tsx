import React from "react";
import { View, Text, TouchableOpacity, Alert } from "react-native";

interface Props {
  children: React.ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.setState({ hasError: true });
    console.error("ErrorBoundary caught an error:", error, errorInfo);
    Alert.alert(
      "Something went wrong",
      "An unexpected error occurred. Please try again.",
      [{ text: "Retry", onPress: this.handleRetry }]
    );
  }

  handleRetry = () => {
    this.setState({ hasError: false });
  };

  render() {
    if (this.state.hasError) {
      return (
        <View className="flex-1 justify-center items-center p-6">
          <TouchableOpacity
            className="bg-blue-600 px-8 py-3 rounded-lg"
            accessibilityLabel="Retry"
            accessibilityRole="button"
            onPress={this.handleRetry}
          >
            <Text className="text-white font-semibold">Retry</Text>
          </TouchableOpacity>
        </View>
      );
    }

    return this.props.children;
  }
}
